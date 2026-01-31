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
from typing import List, Dict, Any, Optional

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
        df: pd.DataFrame,
        indicators: List[str],
        plugins: Dict[str, Any],
        disable_recursive_mapping: bool = False
    ) -> pd.DataFrame:
        """
        Compute a collection of indicators using hybrid parallel execution.

        This method coordinates:
        - Parsing indicator definitions
        - Dispatching calculations to either Polars or Pandas
        - Executing all Polars expressions in a single lazy plan
        - Collecting and merging Pandas results from worker threads
        - Assembling final output in either flat or nested form

        Args:
            df (pd.DataFrame):
                Input DataFrame containing price data or other features.
            indicators (List[str]):
                List of indicator identifiers, including parameters
                (e.g., ["rsi_14", "ema_20"]).
            plugins (Dict[str, Any]):
                Registry mapping indicator names to plugin definitions.
                Each plugin defines how the indicator is calculated.
            disable_recursive_mapping (bool, optional):
                If True, returns a flat DataFrame with one column per indicator.
                If False, nests indicator results into per-row dictionaries.

        Returns:
            pd.DataFrame:
                DataFrame containing computed indicator results merged
                with the original input data.
        """
        # If the input DataFrame is empty, there is nothing to compute
        if df.empty:
            return df

        # Always work on a copy so we never mutate user data
        df = df.copy()

        # Convert 'close' column to numeric if present
        # This prevents string or object dtype issues later
        if 'close' in df.columns:
            df['close'] = pd.to_numeric(df['close'], errors='coerce')

        # Convert Pandas DataFrame to a Polars LazyFrame
        # LazyFrames build an execution plan instead of running immediately
        main_pl = pl.from_pandas(df, rechunk=False).lazy()

        # List of futures for Pandas-based indicators
        pandas_tasks = []

        # List of Polars expressions to apply in one batch
        polars_expressions = []

        # Loop through every requested indicator
        for ind_str in indicators:

            # The indicator name is everything before the first underscore
            # Example: "rsi_14" -> "rsi"
            name = ind_str.split('_')[0]

            # If the indicator is not registered, skip it silently
            if name not in plugins:
                continue

            # Retrieve plugin configuration
            plugin_entry = plugins[name]

            # Parse indicator parameters from the string
            ind_opts = self._resolve_options(ind_str, plugin_entry)

            # Retrieve optional metadata function
            meta_func = plugin_entry.get('meta')

            # Execute metadata function if it exists
            plugin_meta = meta_func() if callable(meta_func) else {}

            # Decide execution engine based on plugin metadata
            if plugin_meta.get('polars', 0):

                # Prefer Polars-native calculation if available
                calc_func_pl = plugin_entry.get(
                    'calculate_polars',
                    plugin_entry.get('calculate')
                )

                # Generate Polars expression(s)
                expr = calc_func_pl(ind_str, ind_opts)

                # Some indicators return multiple expressions
                if isinstance(expr, list):
                    polars_expressions.extend(expr)
                else:
                    polars_expressions.append(expr)

            else:
                # If not self.executor, set it up
                if not self.executor:
                    self.executor = concurrent.futures.ThreadPoolExecutor(
                        max_workers=self.max_workers
                    )

                # Pandas indicators are executed asynchronously in threads
                pandas_tasks.append(
                    self.executor.submit(
                        IndicatorWorker.execute_pandas_task,
                        df_slice=df,
                        p_func=plugin_entry.get('calculate'),
                        full_name=ind_str,
                        p_opts=ind_opts
                    )
                )

        # Apply all Polars expressions in one lazy execution plan
        if polars_expressions:
            main_pl = main_pl.with_columns(polars_expressions)

        # Execute the Polars plan and materialize results
        collected_pl = main_pl.collect()

        # Decide how results should be assembled
        if disable_recursive_mapping:
            return self._assemble_flat(df, collected_pl, pandas_tasks)
        else:
            return self._assemble_nested(df, collected_pl, pandas_tasks)

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
        tasks: List
    ) -> pd.DataFrame:
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
                Flat DataFrame containing original data and indicator columns.
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

        # Convert Polars DataFrame back to Pandas
        return combined_pl.to_pandas(
            use_threads=True,
            types_mapper=pd.ArrowDtype if hasattr(pd, 'ArrowDtype') else None
        )

    def _assemble_nested(
        self,
        df_orig: pd.DataFrame,
        main_pl: pl.DataFrame,
        tasks: List
    ) -> pd.DataFrame:
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
        """

        # Collect completed Pandas indicator results
        pandas_results = [
            f.result()
            for f in concurrent.futures.as_completed(tasks)
            if f.result() is not None
        ]

        # Merge Pandas and Polars indicator outputs
        if pandas_results:
            matrix = pd.concat(pandas_results, axis=1)
            polars_pd = main_pl.select(
                pl.all().exclude(df_orig.columns)
            ).to_pandas()
            matrix = pd.concat([matrix, polars_pd], axis=1)
        else:
            matrix = main_pl.select(
                pl.all().exclude(df_orig.columns)
            ).to_pandas()

        # Remove duplicate columns and round values
        matrix = matrix.loc[:, ~matrix.columns.duplicated()]
        numeric_cols = matrix.select_dtypes(include=[np.number]).columns
        matrix[numeric_cols] = matrix[numeric_cols].round(6)

        # Convert each row into a nested dictionary
        records = matrix.to_dict(orient='records')
        nested_list = []

        for rec in records:
            row_dict = {}

            for k, v in rec.items():
                # Skip NaN values entirely
                if pd.isna(v):
                    continue

                # Group multi-output indicators
                if "__" in k:
                    grp, sub = k.split("__", 1)
                    if grp not in row_dict:
                        row_dict[grp] = {}
                    row_dict[grp][sub] = v
                else:
                    row_dict[k] = v

            nested_list.append(row_dict)

        # Attach nested indicators to original DataFrame
        df_orig['indicators'] = nested_list
        return df_orig


def parallel_indicators(
    df,
    indicators,
    plugins,
    disable_recursive_mapping=False
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
        disable_recursive_mapping
    )
