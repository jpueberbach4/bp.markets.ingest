#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        parallel.py
 Author:      JP Ueberbach
 Created:     2026-01-12
 Update:      2026-01-31 (Polars-Pandas hybrid)

 Description:
     High-performance engine for parallel computation of technical indicators
     over market data using a hybrid Pandas + Polars execution model.

     This module provides a scalable indicator computation pipeline that:
       - Accepts market data as a pandas DataFrame.
       - Supports a plugin-based indicator architecture with both Pandas and
         Polars-native implementations.
       - Executes Polars indicators lazily in a single optimized execution graph
         for maximum columnar performance.
       - Executes Pandas-based indicators concurrently using a thread pool.
       - Normalizes single- and multi-output indicators into a consistent
         naming scheme.
       - Optionally assembles results into either:
           * A flat, column-oriented DataFrame (one column per indicator), or
           * A nested per-row dictionary structure under an "indicators" column.
       - Preserves the original dataset alongside computed indicator outputs.
       - Handles missing data, NaN values, and unequal output lengths safely.
       - Maintains backward compatibility via the `parallel_indicators` wrapper.

     The primary entry point is the `parallel_indicators` function, which
     delegates execution to the `IndicatorEngine` class.

     The polars-pandas hybrid enables users to first develop in the faster-to-
     iterate pandas-way and then when done, convert to high-performance polars.

 Requirements:
     - Python 3.8+
     - pandas
     - numpy
     - polars
     - concurrent.futures

 License:
     MIT License

===============================================================================
"""
import pandas as pd
import numpy as np
import os
import concurrent.futures
import gc
from typing import List, Dict, Any, Optional, Union

# Polars is required for fast, columnar, lazy execution
# We fail immediately if it is not installed so the error is obvious
try:
    import polars as pl
except ImportError:
    raise ImportError("Polars is required. Run 'pip install polars'")


class IndicatorWorker:
    """
    Stateless helper class responsible for executing Pandas-based indicators.

    This class is intentionally stateless and exists solely to encapsulate
    Pandas indicator execution logic so it can be safely run inside a
    ThreadPoolExecutor without shared mutable state.

    All methods in this class must be thread-safe and self-contained.
    """

    @staticmethod
    def execute_pandas_task(
        df_slice: pd.DataFrame,
        p_func: Any,
        full_name: str,
        p_opts: Dict
    ) -> Optional[pd.DataFrame]:
        """
        Execute a Pandas-based indicator function and normalize its output.

        This method is executed inside a worker thread. It calls the
        user-provided Pandas indicator function, validates the result,
        and standardizes column naming so downstream merging logic can
        treat all indicator outputs uniformly.

        Multi-output indicators are flattened by prefixing each output
        column with the full indicator name.

        Args:
            df_slice (pd.DataFrame):
                Input DataFrame slice used for indicator computation.
                Typically this is the full dataset, but it may be a subset
                depending on upstream logic.
            p_func (Any):
                Pandas indicator calculation function provided by a plugin.
                Expected signature: (df: pd.DataFrame, opts: Dict) -> pd.DataFrame.
            full_name (str):
                Fully-qualified indicator name including parameters
                (e.g., "rsi_14", "macd_12_26_9").
            p_opts (Dict):
                Parsed indicator options extracted from the indicator string.

        Returns:
            Optional[pd.DataFrame]:
                A normalized Pandas DataFrame containing indicator results,
                or None if the indicator produced no output or an empty result.
        """

        # Run the indicator calculation using Pandas
        # This is user-provided plugin code
        res_df = p_func(df_slice, p_opts)

        # If the indicator returns nothing or an empty DataFrame,
        # we skip it entirely
        if res_df is None or res_df.empty:
            return None

        # If the indicator produces multiple output columns,
        # prefix each column so we can group them later
        if len(res_df.columns) > 1:
            res_df.columns = [
                f"{full_name}__{c}" for c in res_df.columns
            ]
        else:
            # If there is only one column, just name it after the indicator
            res_df.columns = [full_name]

        # Return the cleaned, normalized DataFrame
        return res_df


class IndicatorEngine:
    """
    Core execution engine for technical indicators.

    This engine orchestrates a hybrid execution model:
    - Polars-native indicators are executed lazily in a single optimized
      execution graph.
    - Pandas-based indicators are executed concurrently using threads.
    - Results from both systems are merged into a unified Pandas DataFrame.

    The engine is designed to maximize performance while maintaining
    backward compatibility with existing Pandas indicator plugins.
    """

    def __init__(self, max_workers: int = None):
        """
        Initialize the indicator execution engine.

        This constructor configures the thread pool used for Pandas-based
        indicator execution.

        Args:
            max_workers (int, optional):
                Maximum number of worker threads to use for Pandas indicators.
                If not provided, defaults to the number of available CPU cores.
        """

        # If max_workers is not provided, fall back to CPU count
        self.max_workers = max_workers or os.cpu_count()

        # Thread pool will go here if we have pandas indicators
        self.executor = None

    def compute(
            self,
            df: Union[pd.DataFrame, pl.DataFrame],
            indicators: List[str],
            plugins: Dict[str, Any],
            disable_recursive_mapping: bool = False,
            return_polars_dataframe: bool = False,
        ) -> Union[pd.DataFrame, pl.DataFrame]:
            """
            Compute a collection of indicators using hybrid parallel execution.
            """
            # Detection of input type
            is_polars = isinstance(df, pl.DataFrame)

            # If the input DataFrame is empty, there is nothing to compute
            if (is_polars and df.is_empty()) or (not is_polars and df.empty):
                return df

            # Only Pandas needs an explicit copy to prevent mutation of the caller's data.
            # Polars handles this via its internal architecture.
            if not is_polars:
                df = df.copy()

            # Convert 'close' column to numeric if present
            if 'close' in df.columns:
                if is_polars:
                    # Polars-native casting (Vectorized)
                    df = df.with_columns(pl.col("close").cast(pl.Float64, strict=False))
                else:
                    # Pandas-native casting
                    df['close'] = pd.to_numeric(df['close'], errors='coerce')

            # Convert Input to a Polars LazyFrame
            if is_polars:
                main_pl = df.lazy()
                df_for_pandas = None 
            else:
                main_pl = pl.from_pandas(df, rechunk=False).lazy()
                df_for_pandas = df

            pandas_tasks = []
            polars_expressions = []

            for ind_str in indicators:
                name = ind_str.split('_')[0]
                if name not in plugins:
                    continue

                plugin_entry = plugins[name]
                ind_opts = self._resolve_options(ind_str, plugin_entry)
                meta_func = plugin_entry.get('meta')
                plugin_meta = meta_func() if callable(meta_func) else {}

                if plugin_meta.get('polars', 0):
                    calc_func_pl = plugin_entry.get('calculate_polars', plugin_entry.get('calculate'))
                    expr = calc_func_pl(ind_str, ind_opts)
                    if isinstance(expr, list):
                        polars_expressions.extend(expr)
                    else:
                        polars_expressions.append(expr)

                else:
                    if not self.executor:
                        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers)

                    # Delayed Pandas conversion: Only run if a legacy indicator is requested
                    if df_for_pandas is None:
                        df_for_pandas = df.to_pandas()

                    pandas_tasks.append(
                        self.executor.submit(
                            IndicatorWorker.execute_pandas_task,
                            df_slice=df_for_pandas,
                            p_func=plugin_entry.get('calculate'),
                            full_name=ind_str,
                            p_opts=ind_opts
                        )
                    )

            # Apply Polars expressions
            if polars_expressions:
                main_pl = main_pl.with_columns(polars_expressions)

            # Execute plan
            collected_pl = main_pl.collect()

            # Final assembly
            if disable_recursive_mapping:
                return self._assemble_flat(df, collected_pl, pandas_tasks, return_polars_dataframe)
            else:
                return self._assemble_nested(df, collected_pl, pandas_tasks, return_polars_dataframe)

    def _resolve_options(self, ind_str: str, plugin_entry: Dict) -> Dict:
        """
        Parse indicator parameters from an indicator identifier string.

        This method extracts positional arguments embedded in the indicator
        name and converts them into a dictionary of options using
        plugin-provided parsing logic when available.

        Example:
            "ema_20" -> {"length": 20}

        Args:
            ind_str (str):
                Full indicator identifier including parameters.
            plugin_entry (Dict):
                Plugin definition containing calculation and parsing metadata.

        Returns:
            Dict:
                Dictionary of parsed indicator options.
        """

        # Split indicator string into parts
        parts = ind_str.split('_')

        # Container for parsed options
        ind_opts = {}

        # Retrieve plugin calculation function
        plugin_func = plugin_entry.get('calculate')

        # Preferred argument parser if explicitly provided
        pos_args_func = plugin_entry.get('position_args')

        # Use plugin-provided argument parser if available
        if callable(pos_args_func):
            ind_opts.update(pos_args_func(parts[1:]))

        # Fallback for legacy plugins that define position_args globally
        elif (
            hasattr(plugin_func, "__globals__")
            and "position_args" in plugin_func.__globals__
        ):
            ind_opts.update(
                plugin_func.__globals__["position_args"](parts[1:])
            )

        return ind_opts

    def _assemble_flat(
        self,
        df_orig: pd.DataFrame,
        main_pl: pl.DataFrame,
        tasks: List,
        return_polars_dataframe: bool = False
    ) -> Union[pd.DataFrame, pl.DataFrame]:
        """
        Assemble indicator outputs into a flat DataFrame.

        In this mode, each indicator produces one or more top-level columns
        in the resulting DataFrame. This is useful for machine learning
        pipelines and tabular analysis.

        Args:
            df_orig (pd.DataFrame):
                Original input DataFrame.
            main_pl (pl.DataFrame):
                Polars DataFrame containing Polars-based indicator results.
            tasks (List):
                List of futures corresponding to Pandas-based indicators.

        Returns:
            pd.DataFrame:
                Flat Pandas DataFrame containing original data and indicator columns.
            pl.DataFrame:
                Flat Polars DataFrame containing original data and indicator columns.

        """

        # Start with Polars results
        indicator_frames = [main_pl]

        # Collect Pandas indicator results as they finish
        for future in concurrent.futures.as_completed(tasks):
            res_df = future.result()

            # Ignore empty indicator outputs
            if res_df is not None:
                p_res = pl.from_pandas(res_df)

                # If Pandas output is shorter, left-pad with nulls
                if len(p_res) < len(df_orig):
                    pad_len = len(df_orig) - len(p_res)
                    pad = pl.DataFrame(
                        {c: [None] * pad_len for c in p_res.columns},
                        schema=p_res.schema
                    )
                    p_res = pl.concat([pad, p_res])

                indicator_frames.append(p_res)

        # Horizontally merge all indicator results
        combined_pl = pl.concat(
            indicator_frames,
            how="horizontal"
        ).rechunk()

        # Identify which columns are indicators (not original data)
        indicator_cols = [
            c for c in combined_pl.columns
            if c not in df_orig.columns
        ]

        # Determine numeric indicator columns (we would like to not round on strings ;)
        numeric_indicator_cols = [
            c for c in indicator_cols 
            if combined_pl.schema[c].is_numeric()
        ]

        # Round indicator values for numerical stability
        if numeric_indicator_cols:
            combined_pl = combined_pl.with_columns(
                [pl.col(c).round(6) for c in numeric_indicator_cols]
            )

        # Return polars dataframe if option is set
        if return_polars_dataframe:
            return combined_pl
        
        # Convert Polars DataFrame back to Pandas
        return combined_pl.to_pandas(
            use_threads=True,
            types_mapper=pd.ArrowDtype if hasattr(pd, 'ArrowDtype') else None
        )

    def _assemble_nested(
        self,
        df_orig: pd.DataFrame,
        main_pl: pl.DataFrame,
        tasks: List,
        return_polars_dataframe: bool = False
    ) -> Union[pd.DataFrame, pl.DataFrame]:
        """
        Assemble indicator outputs into nested dictionaries per row.

        In this mode, all indicator values for a row are grouped into a
        single dictionary and attached to the original DataFrame under
        the 'indicators' column.

        Multi-output indicators are grouped into sub-dictionaries.

        Args:
            df_orig (pd.DataFrame):
                Original input DataFrame.
            main_pl (pl.DataFrame):
                Polars DataFrame containing Polars-based indicator results.
            tasks (List):
                List of futures corresponding to Pandas-based indicators.

        Returns:
            pd.DataFrame:
                Original DataFrame with an added 'indicators' column
                containing nested indicator dictionaries.
            pl.DataFrame:
                Original Polars DataFrame with an added 'indicators' column
                containing nested indicator dictionaries.
        """

        # Collect completed Pandas indicator results
        pandas_results = [f.result() for f in concurrent.futures.as_completed(tasks) if f.result() is not None]
        
        if pandas_results:
            # Vectorized merge of all indicator columns
            indicator_pl = pl.from_pandas(pd.concat(pandas_results, axis=1))
            # Horizontal concat is very fast in Polars (zero-copy if possible)
            main_pl = pl.concat([main_pl, indicator_pl], how="horizontal")

        # Exclude original OHLCV columns to isolate indicator columns
        indicator_cols = [c for c in main_pl.columns if c not in df_orig.columns]
        
        # Round all numeric indicators in one shot
        main_pl = main_pl.with_columns(
            pl.col(indicator_cols).map_batches(lambda s: s.round(6))
        )

        # Create the Nested Structure
        groups = {}
        standalone = []
        for col in indicator_cols:
            if "__" in col:
                grp, sub = col.split("__", 1)
                groups.setdefault(grp, []).append(col)
            else:
                standalone.append(col)

        # Build the 'indicators' struct column
        struct_exprs = []
        
        # Add standalone indicators
        for col in standalone:
            struct_exprs.append(pl.col(col))
            
        # Add grouped sub-structs (nested dictionaries)
        for grp, cols in groups.items():
            # This creates row_dict[grp] = {sub1: v1, sub2: v2}
            struct_exprs.append(
                pl.struct([pl.col(c).alias(c.split("__", 1)[1]) for c in cols]).alias(grp)
            )

        # Final assembly
        result_pl = main_pl.with_columns(
            pl.struct(struct_exprs).alias("indicators")
        ).select([*df_orig.columns, "indicators"])

        if return_polars_dataframe:
            return result_pl
        
        # Only convert to Pandas at the very last microsecond if requested
        return result_pl.to_pandas()


def parallel_indicators(
    df,
    indicators,
    plugins,
    disable_recursive_mapping:bool=False,
    return_polars_dataframe:bool= False
):
    """
    Backward-compatible convenience wrapper for IndicatorEngine.

    This function preserves the legacy API while internally delegating
    all computation to an IndicatorEngine instance.

    Args:
        df (pd.DataFrame):
            Input DataFrame containing price or feature data.
        indicators (List[str]):
            List of indicator identifiers to compute.
        plugins (Dict[str, Any]):
            Indicator plugin registry.
        disable_recursive_mapping (bool, optional):
            Controls whether indicator outputs are flat or nested.

    Returns:
        pd.DataFrame:
            DataFrame containing computed indicator results.
    """

    # Create engine instance
    engine = IndicatorEngine()

    # Execute indicator computation
    return engine.compute(
        df,
        indicators,
        plugins,
        disable_recursive_mapping,
        return_polars_dataframe
    )
