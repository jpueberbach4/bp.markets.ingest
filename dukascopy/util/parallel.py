#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        parallel.py
 Author:      JP Ueberbach
 Created:     2026-01-12
 Updated:     2026-02-11

 Description:
      Hybrid parallel execution engine for technical indicator computation.
      
      OPTIMIZED VERSION:
      - Native LazyFrame recursion support (no materialization in loops)
      - Empty-task short-circuiting (avoids phantom collects)
      - Robust error handling for mixed Pandas/Polars plugins

===============================================================================
"""

import pandas as pd
import numpy as np
import os
import concurrent.futures
import logging
import warnings
from typing import List, Dict, Any, Optional, Union

try:
    import polars as pl
except ImportError:
    raise ImportError("Polars is required. Run 'pip install polars'")

logger = logging.getLogger(__name__)


class IndicatorWorker:
    """
    Stateless helper responsible for executing Pandas-based indicators.
    """

    @staticmethod
    def execute_pandas_task(
        df_slice: Union[pd.DataFrame, pl.DataFrame],
        p_func: Any,
        full_name: str,
        p_opts: Dict
    ) -> Optional[Union[pd.DataFrame, pl.DataFrame, pl.LazyFrame]]:
        try:
            res_df = p_func(df_slice, p_opts)
            if res_df is None:
                return None

            # Handle Polars result (DataFrame or LazyFrame)
            if isinstance(res_df, (pl.DataFrame, pl.LazyFrame)):
                if isinstance(res_df, pl.LazyFrame):
                    # Use collect_schema() to avoid schema resolution warnings
                    columns = res_df.collect_schema().names()
                    if len(columns) > 1:
                        res_df = res_df.rename({c: f"{full_name}__{c}" for c in columns})
                    else:
                        res_df = res_df.rename({columns[0]: full_name})
                else:
                    if res_df.is_empty(): return None
                    if len(res_df.columns) > 1:
                        res_df = res_df.rename({c: f"{full_name}__{c}" for c in res_df.columns})
                    else:
                        res_df = res_df.rename({res_df.columns[0]: full_name})

            # Handle Pandas result
            else:
                if res_df.empty:
                    return None
                if len(res_df.columns) > 1:
                    res_df.columns = [f"{full_name}__{c}" for c in res_df.columns]
                else:
                    res_df.columns = [full_name]

            return res_df

        except Exception as e:
            logger.error(f"Failed to execute indicator '{full_name}': {str(e)}")
            import traceback
            traceback.print_exc()
            return None


class IndicatorEngine:
    """
    Core execution engine for technical indicators.
    """

    def __init__(self, max_workers: int = None):
        self.max_workers = max_workers or os.cpu_count()
        self.executor = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()

    def shutdown(self):
        if self.executor:
            self.executor.shutdown(wait=True)
            self.executor = None

    def compute(
        self,
        df: Union[pd.DataFrame, pl.DataFrame, pl.LazyFrame],
        indicators: List[str],
        plugins: Dict[str, Any],
        disable_recursive_mapping: bool = False,
        return_polars: bool = False,
        lazy: bool = False,
    ) -> Union[pd.DataFrame, pl.DataFrame, pl.LazyFrame]:
        
        # Detect input type
        is_polars_input = isinstance(df, (pl.DataFrame, pl.LazyFrame))

        if is_polars_input:
            if isinstance(df, pl.DataFrame) and df.is_empty():
                return df
            
            df_polars_source = df
            main_pl = df.lazy() if isinstance(df, pl.DataFrame) else df
            df_for_pandas = None
        else:
            if hasattr(df, 'empty') and df.empty:
                return df

            # Convert to Polars once + Rechunk for SIMD
            df_polars_source = pl.from_pandas(df).rechunk()
            main_pl = df_polars_source.lazy()
            df_for_pandas = df.copy()

        pandas_tasks = []
        polars_expressions = []

        # Process indicators
        for ind_str in indicators:
            name = ind_str.split('_')[0]
            if name not in plugins:
                continue

            plugin_entry = plugins[name]
            ind_opts = self._resolve_options(ind_str, plugin_entry)
            
            meta_func = plugin_entry.get('meta')
            plugin_meta = meta_func() if callable(meta_func) else {}

            # FAST PATH: Polars Native
            if plugin_meta.get('polars', 0):
                calc_func_pl = plugin_entry.get('calculate_polars')
                if not calc_func_pl: continue

                expr = calc_func_pl(ind_str, ind_opts)
                if isinstance(expr, list):
                    polars_expressions.extend(expr)
                else:
                    polars_expressions.append(expr)

            # SLOW PATH: Threaded (Pandas/Legacy)
            else:
                calc_func_df = plugin_entry.get('calculate')
                if not calc_func_df: continue

                if not self.executor:
                    self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers)

                # Prepare input view
                if plugin_meta.get('polars_input', False):
                    # Legacy Polars plugins might need concrete data
                    if isinstance(df_polars_source, pl.LazyFrame):
                        task_input = df_polars_source.collect()
                    elif isinstance(df_polars_source, pl.DataFrame):
                        task_input = df_polars_source.clone()
                    else:
                        task_input = df_polars_source
                else:
                    if df_for_pandas is None:
                        if isinstance(df_polars_source, pl.LazyFrame):
                            df_for_pandas = df_polars_source.collect().to_pandas()
                        else:
                            df_for_pandas = df_polars_source.to_pandas()
                    task_input = df_for_pandas

                pandas_tasks.append(
                    self.executor.submit(
                        IndicatorWorker.execute_pandas_task,
                        df_slice=task_input,
                        p_func=calc_func_df,
                        full_name=ind_str,
                        p_opts=ind_opts
                    )
                )

        # Inject Expressions
        if polars_expressions:
            main_pl = main_pl.with_columns(polars_expressions)

        # Assemble Result
        if disable_recursive_mapping:
            return self._assemble_flat(df, main_pl, pandas_tasks, return_polars, lazy)
        else:
            return self._assemble_nested(df, main_pl, pandas_tasks, return_polars, lazy)

    def _resolve_options(self, ind_str: str, plugin_entry: Dict) -> Dict:
        parts = ind_str.split('_')
        ind_opts = {}
        plugin_func = plugin_entry.get('calculate')
        pos_args_func = plugin_entry.get('position_args')

        if callable(pos_args_func):
            ind_opts.update(pos_args_func(parts[1:]))
        elif hasattr(plugin_func, "__globals__") and "position_args" in plugin_func.__globals__:
            ind_opts.update(plugin_func.__globals__["position_args"](parts[1:]))

        return ind_opts

    def _process_pandas_results(
        self,
        tasks: List,
        df_orig: Union[pd.DataFrame, pl.DataFrame, pl.LazyFrame]
    ) -> List[pl.LazyFrame]:
        
        # OPTIMIZATION: Short-circuit if no tasks exist (avoids phantom collect)
        if not tasks:
            return []

        aligned_results = []
        
        # Determine reference height
        if isinstance(df_orig, pl.DataFrame):
            height_ref = df_orig.height
        elif isinstance(df_orig, pl.LazyFrame):
            height_ref = df_orig.select(pl.len()).collect().item()
        else:
            height_ref = len(df_orig)

        for future in concurrent.futures.as_completed(tasks):
            try:
                res_df = future.result()
                if res_df is None: continue

                # Normalize to LazyFrame
                current_len = None
                if isinstance(res_df, pd.DataFrame):
                    current_len = len(res_df)
                    p_res = pl.from_pandas(res_df).lazy()
                elif isinstance(res_df, pl.DataFrame):
                    current_len = res_df.height
                    p_res = res_df.lazy()
                else:
                    p_res = res_df 

                # If length unknown, fetch it
                if current_len is None:
                    current_len = p_res.select(pl.len()).collect().item()

                # Padding logic
                if current_len < height_ref:
                    pad_len = height_ref - current_len
                    schema = p_res.collect_schema() 
                    pad = pl.DataFrame(
                        {c: [None]*pad_len for c in schema.names()}, 
                        schema=schema
                    ).lazy()
                    p_res = pl.concat([pad, p_res])

                aligned_results.append(p_res)

            except Exception as e:
                logger.error(f"Error processing future result: {str(e)}")
                continue

        return aligned_results

    def _assemble_flat(
            self,
            df_orig: Union[pd.DataFrame, pl.DataFrame, pl.LazyFrame],
            main_pl: pl.LazyFrame,
            tasks: List,
            return_polars: bool = False,
            lazy: bool = False
     ) -> Union[pd.DataFrame, pl.DataFrame, pl.LazyFrame]:
        
        indicator_frames = [main_pl]
        indicator_frames.extend(self._process_pandas_results(tasks, df_orig))
        combined_lf = pl.concat(indicator_frames, how="horizontal")
        
        if lazy: return combined_lf

        combined_pl = combined_lf.collect()
        if return_polars: return combined_pl

        return combined_pl.to_pandas(
            use_threads=True,
            types_mapper=pd.ArrowDtype if hasattr(pd, 'ArrowDtype') else None
        )

    def _assemble_nested(
        self,
        df_orig: Union[pd.DataFrame, pl.DataFrame, pl.LazyFrame],
        main_pl: pl.LazyFrame,
        tasks: List,
        return_polars: bool = False,
        lazy: bool = False
    ) -> Union[pd.DataFrame, pl.DataFrame, pl.LazyFrame]:
        
        aligned_pandas_results = self._process_pandas_results(tasks, df_orig)
        if aligned_pandas_results:
            indicator_lf = pl.concat(aligned_pandas_results, how="horizontal")
            main_pl = pl.concat([main_pl, indicator_lf], how="horizontal")

        all_cols = main_pl.collect_schema().names()
        
        # Identify new columns
        if isinstance(df_orig, pl.LazyFrame):
            orig_cols = df_orig.collect_schema().names()
        elif isinstance(df_orig, pl.DataFrame):
            orig_cols = df_orig.columns
        else:
            orig_cols = df_orig.columns

        indicator_cols = [c for c in all_cols if c not in orig_cols]
        groups = {}
        standalone = []

        for col in indicator_cols:
            if "__" in col:
                grp, sub = col.split("__", 1)
                groups.setdefault(grp, []).append(col)
            else:
                standalone.append(col)

        struct_exprs = []
        for col in standalone:
            struct_exprs.append(pl.col(col))

        for grp, cols in groups.items():
            struct_exprs.append(
                pl.struct(
                    [pl.col(c).alias(c.split("__", 1)[1]) for c in cols]
                ).alias(grp)
            )

        result_lf = main_pl.with_columns(
            pl.struct(struct_exprs).alias("indicators")
        ).select([*orig_cols, "indicators"])
        
        if lazy: return result_lf

        result_pl = result_lf.collect()
        if return_polars: return result_pl

        return result_pl.to_pandas(use_threads=True)


def parallel_indicators(
    df,
    indicators,
    plugins,
    disable_recursive_mapping: bool = False,
    return_polars: bool = False,
    lazy: bool = False,
):
    with IndicatorEngine() as engine:
        return engine.compute(
            df,
            indicators,
            plugins,
            disable_recursive_mapping,
            return_polars,
            lazy
        )