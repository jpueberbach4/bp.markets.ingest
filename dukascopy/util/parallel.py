#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        parallel.py
 Author:      JP Ueberbach
 Created:     2026-01-12
 Updated:     2026-01-31

 Description:
     Hybrid parallel execution engine for technical indicator computation.

     This module implements a unified, high-performance pipeline for computing
     technical indicators that may be implemented in either Pandas or Polars.

     The engine transparently supports both execution models:
       - Polars-native indicators are executed lazily inside a single optimized
         Polars execution graph and collected exactly once.
       - Legacy Pandas indicators are executed concurrently using a thread pool
         and merged back into the result without blocking Polars execution.

     Key responsibilities of this module:
       - Automatically detect whether the input data is Pandas or Polars
       - Dispatch each indicator to the correct execution backend
       - Normalize indicator output naming to avoid column collisions
       - Safely handle warmup periods and missing data
       - Preserve row alignment between all indicator outputs
       - Support both flat outputs and nested per-row indicator structures
       - Minimize data copying and avoid unnecessary conversions

     Design goals:
       - Enable rapid prototyping and experimentation using Pandas
       - Provide a seamless upgrade path to Polars for production workloads
       - Maximize performance by batching Polars expressions and parallelizing
         Pandas execution only when required
       - Maintain backward compatibility with existing indicator plugins

     This architecture allows mixed Pandas/Polars indicator sets to coexist
     without sacrificing correctness, performance, or developer ergonomics.

 Requirements:
     - Python 3.8+
     - pandas
     - numpy
     - polars

 License:
     MIT License
===============================================================================
"""

import pandas as pd
import numpy as np
import os
import concurrent.futures
import polars.selectors as cs
from typing import List, Dict, Any, Optional, Union

# Polars is required for the high-performance execution path.
# Fail early with a clear message if it is missing.
try:
    import polars as pl
except ImportError:
    raise ImportError("Polars is required. Run 'pip install polars'")


# TODO: configuration based?
POLARS_ROUNDING = 6

class IndicatorWorker:
    """
    Stateless helper responsible for executing Pandas-based indicators.

    This class exists only to isolate Pandas execution so it can be safely
    submitted to a ThreadPoolExecutor without shared mutable state.
    """

    @staticmethod
    def execute_pandas_task(
        df_slice: pd.DataFrame,
        p_func: Any,
        full_name: str,
        p_opts: Dict
    ) -> Optional[pd.DataFrame]:
        """
        Execute a Pandas-based indicator and normalize its output columns.

        Args:
            df_slice (pd.DataFrame): Full market data passed to the indicator.
            p_func (Callable): The plugin's Pandas `calculate` function.
            full_name (str): Full indicator name including parameters.
            p_opts (Dict): Parsed indicator options.

        Returns:
            Optional[pd.DataFrame]: Normalized indicator output or None if empty.
        """

        # Call the plugin's Pandas implementation.
        # This may perform slicing, rolling windows, warmups, etc internally.
        res_df = p_func(df_slice, p_opts)

        # If the indicator explicitly returns nothing, or produced no rows,
        # we treat it as a no-op and exclude it from the final output.
        if res_df is None or res_df.empty:
            return None

        # Normalize output column names to avoid collisions between indicators.
        #
        # Multi-output indicators must be namespaced using:
        #   <indicator_name>__<subcolumn>
        #
        # This ensures:
        #   - Deterministic column names
        #   - No accidental overwrites when merging results
        if len(res_df.columns) > 1:
            res_df.columns = [f"{full_name}__{c}" for c in res_df.columns]
        else:
            res_df.columns = [full_name]

        return res_df


class IndicatorEngine:
    """
    Core execution engine for technical indicators.

    This class orchestrates hybrid execution:
      - Polars indicators are executed lazily in one optimized graph
      - Pandas indicators are executed concurrently in worker threads
    """

    def __init__(self, max_workers: int = None):
        """
        Initialize the indicator engine.

        Args:
            max_workers (int, optional): Maximum number of worker threads
                for Pandas indicators. Defaults to CPU core count.
        """
        # Default to CPU core count if no explicit limit is provided.
        self.max_workers = max_workers or os.cpu_count()

        # ThreadPoolExecutor is created lazily so we pay the cost
        # only if Pandas indicators are actually used.
        self.executor = None

    def compute(
        self,
        df: Union[pd.DataFrame, pl.DataFrame],
        indicators: List[str],
        plugins: Dict[str, Any],
        disable_recursive_mapping: bool = False,
        return_polars: bool = False,
    ) -> Union[pd.DataFrame, pl.DataFrame]:
        """
        Compute multiple indicators using hybrid parallel execution.

        Args:
            df (Union[pd.DataFrame, pl.DataFrame]): Input market data.
            indicators (List[str]): Indicator identifiers (e.g. "rsi_14").
            plugins (Dict[str, Any]): Loaded indicator plugins.
            disable_recursive_mapping (bool): If True, return flat output.
            return_polars (bool): If True, return Polars DataFrame.

        Returns:
            Union[pd.DataFrame, pl.DataFrame]: DataFrame with indicator results.
        """

        # Determine execution mode based on input type.
        # This single flag drives the entire pipeline.
        is_polars = isinstance(df, pl.DataFrame)

        # Short-circuit empty inputs to avoid unnecessary setup work.
        if is_polars:
            if df.is_empty():
                return df
        elif df.empty:
            return df

        # Pandas DataFrames are mutable and passed by reference.
        # We defensively copy to avoid mutating user-owned data.
        if not is_polars:
            df = df.copy()

        # Many indicators assume "ohlcv" is numeric.
        # We coerce here once to avoid repeated conversions downstream.
        if is_polars:
            # strict=False prevents hard failures on bad data
            df = df.with_columns(
                pl.col("open").cast(pl.Float64, strict=False),
                pl.col("high").cast(pl.Float64, strict=False),
                pl.col("low").cast(pl.Float64, strict=False),
                pl.col("close").cast(pl.Float64, strict=False),
                pl.col("volume").cast(pl.Float64, strict=False)
            )
        else:
            # Non-numeric values become NaN
            df['open'] = pd.to_numeric(df['open'], errors='coerce')
            df['high'] = pd.to_numeric(df['high'], errors='coerce')
            df['low'] = pd.to_numeric(df['low'], errors='coerce')
            df['close'] = pd.to_numeric(df['close'], errors='coerce')
            df['volume'] = pd.to_numeric(df['volume'], errors='coerce')

        # Build the Polars execution graph.
        #
        # Even for Pandas input, we convert once to Polars so that:
        #   - All Polars-native indicators share one optimized graph
        #   - We only collect once at the end
        if is_polars:
            main_pl = df.lazy()
            df_for_pandas = None
        else:
            main_pl = pl.from_pandas(df, rechunk=False).lazy()
            df_for_pandas = df

        # Containers for deferred execution.
        pandas_tasks = []        # Futures for threaded Pandas indicators
        polars_expressions = []  # Lazy Polars expressions

        # Iterate over each requested indicator identifier.
        for ind_str in indicators:
            # Extract the base indicator name (before parameters).
            name = ind_str.split('_')[0]

            # Silently ignore unknown indicators.
            if name not in plugins:
                continue

            plugin_entry = plugins[name]

            # Parse positional parameters encoded in the indicator string.
            ind_opts = self._resolve_options(ind_str, plugin_entry)

            # Retrieve plugin metadata to determine execution backend.
            meta_func = plugin_entry.get('meta')
            plugin_meta = meta_func() if callable(meta_func) else {}

            # Polars-native indicators: build expressions only.
            if plugin_meta.get('polars', 0):
                calc_func_pl = plugin_entry.get(
                    'calculate_polars',
                    plugin_entry.get('calculate')
                )

                # No computation happens here — expressions are just appended.
                expr = calc_func_pl(ind_str, ind_opts)

                # Support both single- and multi-expression indicators.
                if isinstance(expr, list):
                    polars_expressions.extend(expr)
                else:
                    polars_expressions.append(expr)

            # Pandas-based indicators: execute concurrently.
            else:
                # Initialize the thread pool lazily.
                if not self.executor:
                    self.executor = concurrent.futures.ThreadPoolExecutor(
                        max_workers=self.max_workers
                    )

                # Convert Polars → Pandas only once, and only if required.
                if df_for_pandas is None:
                    df_for_pandas = df.to_pandas()

                # Submit the indicator execution to the thread pool.
                pandas_tasks.append(
                    self.executor.submit(
                        IndicatorWorker.execute_pandas_task,
                        df_slice=df_for_pandas,
                        p_func=plugin_entry.get('calculate'),
                        full_name=ind_str,
                        p_opts=ind_opts
                    )
                )

        # Attach all collected Polars expressions to the graph.
        batch_size = 100
        for i in range(0, len(polars_expressions), batch_size):
            batch = polars_expressions[i : i + batch_size]
            main_pl = main_pl.with_columns(batch)

        # Execute the Polars graph exactly once.
        collected_pl = main_pl.collect()

        # Assemble final output according to the requested format.
        if disable_recursive_mapping:
            return self._assemble_flat(
                df, collected_pl, pandas_tasks, return_polars
            )
        else:
            return self._assemble_nested(
                df, collected_pl, pandas_tasks, return_polars
            )

    def _resolve_options(self, ind_str: str, plugin_entry: Dict) -> Dict:
        """
        Extract indicator parameters from an indicator identifier string.

        Args:
            ind_str (str): Indicator string (e.g. "bbands_20_2.0").
            plugin_entry (Dict): Plugin module entry.

        Returns:
            Dict: Parsed indicator options.
        """
        parts = ind_str.split('_')
        ind_opts = {}

        plugin_func = plugin_entry.get('calculate')
        pos_args_func = plugin_entry.get('position_args')

        # Preferred modern API: explicit position_args callable.
        if callable(pos_args_func):
            ind_opts.update(pos_args_func(parts[1:]))

        # Legacy fallback for older plugins.
        elif (
            hasattr(plugin_func, "__globals__")
            and "position_args" in plugin_func.__globals__
        ):
            ind_opts.update(
                plugin_func.__globals__["position_args"](parts[1:])
            )

        return ind_opts

    def _process_pandas_results(
        self,
        tasks: List,
        df_orig: pd.DataFrame
    ) -> List[pl.DataFrame]:
        """
        Helper to collect Pandas results, convert to Polars, and align row counts.

        Iterates through completed futures, converts the results to Polars DataFrames,
        and ensures they are padded with nulls if they are shorter than the original
        DataFrame (handling warmup periods).

        Args:
            tasks (List): List of futures from the ThreadPoolExecutor.
            df_orig (pd.DataFrame): Original dataframe for height reference.

        Returns:
            List[pl.DataFrame]: List of aligned Polars DataFrames.
        """
        aligned_results = []
        for future in concurrent.futures.as_completed(tasks):
            res_df = future.result()

            if res_df is not None:
                p_res = pl.from_pandas(res_df)

                # Pandas indicators may return fewer rows due to warmup.
                # We left-pad with nulls so row alignment matches input.
                if p_res.height < len(df_orig):
                    pad_len = len(df_orig) - p_res.height
                    pad = pl.DataFrame(
                        {c: [None] * pad_len for c in p_res.columns},
                        schema=p_res.schema
                    )
                    p_res = pl.concat([pad, p_res])

                aligned_results.append(p_res)
        return aligned_results

    def _round_numeric_indicators(
        self,
        df: pl.DataFrame,
        indicator_cols: List[str]
    ) -> pl.DataFrame:
        """
        Round numeric indicator columns to 6 decimal places.

        This optimizes performance by using Polars selectors and ensures
        that only indicator columns (not original market data) are modified.

        Args:
            df (pl.DataFrame): DataFrame containing indicators.
            indicator_cols (List[str]): List of column names identified as indicators.

        Returns:
            pl.DataFrame: DataFrame with rounded indicator columns.
        """
        # Optimization: Use selectors instead of schema iteration
        numeric_cols = df.select(cs.numeric()).columns
        
        # Filter to ensure we only round indicator columns, not original data
        numeric_indicator_cols = [c for c in numeric_cols if c in indicator_cols]

        if numeric_indicator_cols:
            return df.with_columns(
                [pl.col(c).round(POLARS_ROUNDING) for c in numeric_indicator_cols]
            )
        return df

    def _assemble_flat(
            self,
            df_orig: pd.DataFrame,
            main_pl: pl.DataFrame,
            tasks: List,
            return_polars: bool = False
     ) -> Union[pd.DataFrame, pl.DataFrame]:
        """
        Assemble all indicator outputs into a flat DataFrame.

        This method merges results coming from two different execution paths:
        1) Polars-native indicators that were executed lazily and already
        collected into `main_pl`.
        2) Pandas-based indicators that were executed concurrently in threads
        and returned as futures.

        Pandas indicator outputs may be shorter than the original input data
        due to warmup requirements. In that case, the results are left-padded
        with null values so that all indicator columns align correctly with
        the original input rows.

        All indicator outputs are merged horizontally into a single DataFrame.
        Numeric indicator values are rounded for cleaner output.

        Args:
            df_orig (pd.DataFrame): The original input DataFrame used to compute
                indicators. Used to determine row count and identify non-
                indicator (market data) columns.
            main_pl (pl.DataFrame): Collected Polars DataFrame containing all
                Polars-native indicator results.
            tasks (List): List of Future objects representing running or
                completed Pandas-based indicator computations.
            return_polars (bool): If True, return a Polars DataFrame
                instead of converting the result back to Pandas.

        Returns:
            Union[pd.DataFrame, pl.DataFrame]: A flat DataFrame containing the
            original market data columns and all indicator outputs as separate
            columns.
        """
        # Start with the Polars results (already aligned to input rows).
        indicator_frames = [main_pl]

        # Collect and align Pandas results
        indicator_frames.extend(self._process_pandas_results(tasks, df_orig))

        # Merge all indicator outputs horizontally.
        combined_pl = pl.concat(indicator_frames, how="horizontal").rechunk()

        # Identify indicator columns by excluding original input columns.
        indicator_cols = [
            c for c in combined_pl.columns
            if c not in df_orig.columns
        ]

        # Apply rounding to numeric indicator columns
        combined_pl = self._round_numeric_indicators(combined_pl, indicator_cols)

        if return_polars:
            return combined_pl

        # Convert back to Pandas only at the very end.
        return combined_pl.to_pandas(
            use_threads=True,
            types_mapper=pd.ArrowDtype if hasattr(pd, 'ArrowDtype') else None
        )

    def _assemble_nested(
        self,
        df_orig: pd.DataFrame,
        main_pl: pl.DataFrame,
        tasks: List,
        return_polars: bool = False
    ) -> Union[pd.DataFrame, pl.DataFrame]:
        """
        Assemble indicator outputs into a nested per-row structure.

        This method combines indicator results from both execution backends
        (Polars-native and Pandas-based) and organizes them into a single
        structured column named ``indicators``.

        Indicator columns are grouped based on their naming convention:
        - Single-output indicators (no "__" in the column name) are placed
          directly at the top level of the ``indicators`` struct.
        - Multi-output indicators (using the "__" separator) are grouped into
          nested structs, with the prefix acting as the indicator name.

        Numeric indicator values are rounded for consistency and cleaner
        downstream consumption. The final output preserves all original
        market data columns and adds a single nested ``indicators`` column.

        Args:
            df_orig (pd.DataFrame): The original input DataFrame containing
                market data. Used to distinguish indicator columns from
                non-indicator columns.
            main_pl (pl.DataFrame): Polars DataFrame containing collected
                Polars-native indicator results.
            tasks (List): List of Future objects representing completed or
                pending Pandas-based indicator computations.
            return_polars (bool): If True, return a Polars DataFrame
                instead of converting the result to Pandas.

        Returns:
            Union[pd.DataFrame, pl.DataFrame]: A DataFrame where each row
            contains the original market data and a nested ``indicators``
            object holding all computed indicator values.
        """
        # Collect Pandas results and align them to the original row count
        aligned_pandas_results = self._process_pandas_results(tasks, df_orig)

        # Merge aligned Pandas outputs into the Polars result.
        if aligned_pandas_results:
            # Concat all pandas results horizontally first
            indicator_pl = pl.concat(aligned_pandas_results, how="horizontal")
            # Then merge with the main Polars frame
            main_pl = pl.concat([main_pl, indicator_pl], how="horizontal")

        # Identify indicator columns.
        indicator_cols = [
            c for c in main_pl.columns
            if c not in df_orig.columns
        ]

        # Apply rounding to numeric indicator columns
        main_pl = self._round_numeric_indicators(main_pl, indicator_cols)

        groups = {}
        standalone = []

        # Group multi-output indicators by their namespace prefix.
        for col in indicator_cols:
            if "__" in col:
                grp, sub = col.split("__", 1)
                groups.setdefault(grp, []).append(col)
            else:
                standalone.append(col)

        struct_exprs = []

        # Standalone indicators become top-level struct fields.
        for col in standalone:
            struct_exprs.append(pl.col(col))

        # Multi-output indicators become nested structs.
        for grp, cols in groups.items():
            struct_exprs.append(
                pl.struct(
                    [pl.col(c).alias(c.split("__", 1)[1]) for c in cols]
                ).alias(grp)
            )

        # Pack everything into a single "indicators" column.
        result_pl = main_pl.with_columns(
            pl.struct(struct_exprs).alias("indicators")
        ).select([*df_orig.columns, "indicators"])

        if return_polars:
            return result_pl

        return result_pl.to_pandas()


def parallel_indicators(
    df,
    indicators,
    plugins,
    disable_recursive_mapping: bool = False,
    return_polars: bool = False
):
    """
    Backward-compatible wrapper around IndicatorEngine.

    Args:
        df (pd.DataFrame or pl.DataFrame): Input market data.
        indicators (List[str]): Indicator identifiers.
        plugins (Dict[str, Any]): Loaded plugins.
        disable_recursive_mapping (bool): Return flat output if True.
        return_polars (bool): Return Polars DataFrame if True.

    Returns:
        Union[pd.DataFrame, pl.DataFrame]: Indicator results.
    """
    engine = IndicatorEngine()

    return engine.compute(
        df,
        indicators,
        plugins,
        disable_recursive_mapping,
        return_polars
    )