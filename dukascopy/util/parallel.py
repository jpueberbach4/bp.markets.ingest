#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        parallel.py
 Author:      JP Ueberbach
 Created:     2026-01-12
 Updated:     2026-02-10

 Description:
      Hybrid parallel execution engine for technical indicator computation.

      This module provides a unified, high-performance pipeline for computing
      technical indicators implemented across mixed execution backends
      (Polars and Pandas).

      The engine automatically selects the optimal execution strategy
      per indicator:

        - Polars-native indicators are injected directly into a single lazy
          Polars execution graph and evaluated exactly once.
        - Legacy or complex Pandas-based indicators are executed eagerly in
          parallel using a thread pool and merged back into the final result.

      Both execution paths operate concurrently without blocking each other.

 Core responsibilities:
      - Accept Pandas or Polars input transparently
      - Route each indicator to the correct execution backend
      - Minimize data copying via shared Arrow-backed memory
      - Normalize indicator output naming to prevent column collisions
      - Preserve strict row alignment across all indicator outputs
      - Safely handle warmup periods, missing values, and partial results
      - Support both flat outputs and nested per-row indicator structures

 Design goals:
      - Enable rapid prototyping with Pandas-based indicators
      - Provide a seamless upgrade path to Polars for production workloads
      - Maximize performance by batching Polars expressions and isolating
        Pandas execution to parallel worker threads
      - Maintain backward compatibility with existing plugin APIs
      - Avoid unnecessary conversions and materializations

      This architecture allows mixed Pandas/Polars indicator sets to coexist
      in a single computation pipeline without sacrificing correctness,
      performance, or developer ergonomics.

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
import logging
import warnings
from typing import List, Dict, Any, Optional, Union

# Polars is required for the high-performance execution path.
# Fail early with a clear message if it is missing.
try:
    import polars as pl
except ImportError:
    raise ImportError("Polars is required. Run 'pip install polars'")

# Configure a module-level logger for robust error reporting
logger = logging.getLogger(__name__)


class IndicatorWorker:
    """
    Stateless helper responsible for executing Pandas-based indicators.

    This class exists only to isolate Pandas execution so it can be safely
    submitted to a ThreadPoolExecutor without shared mutable state.
    """

    @staticmethod
    def execute_pandas_task(
        df_slice: Union[pd.DataFrame, pl.DataFrame],
        p_func: Any,
        full_name: str,
        p_opts: Dict
    ) -> Optional[Union[pd.DataFrame, pl.DataFrame]]:
        """Execute a plugin task and normalize its DataFrame output.

        This function runs a plugin calculation that may operate on either a
        pandas or Polars DataFrame. It handles early exits for null or empty
        results and normalizes column names so downstream consumers can safely
        merge results without collisions.

        It includes a robust try/except block to ensure that a failure in one
        specific indicator plugin does not crash the entire execution pipeline.

        Args:
            df_slice: Input DataFrame passed to the plugin. This may be a pandas
                DataFrame or a Polars DataFrame depending on plugin capabilities.
            p_func: The plugin function to execute. It must accept
                `(df_slice, p_opts)` and return a DataFrame or None.
            full_name: Fully-qualified indicator name used to prefix or assign
                output column names.
            p_opts: Dictionary of options forwarded to the plugin function.

        Returns:
            A pandas or Polars DataFrame with normalized column names, or None
            if the plugin produces no usable output.
        """
        try:
            # Run the plugin function using the provided data slice and options
            res_df = p_func(df_slice, p_opts)

            # If the plugin explicitly returned nothing, stop immediately
            if res_df is None:
                return None

            if isinstance(res_df, pl.LazyFrame):
                res_df = res_df.collect()

            # Handle the case where the plugin returned a Polars DataFrame
            if isinstance(res_df, pl.DataFrame):
                # Polars has its own way of checking for emptiness
                if res_df.is_empty():
                    return None

                # If the result has multiple columns, prefix each one
                if len(res_df.columns) > 1:
                    res_df = res_df.rename({
                        c: f"{full_name}__{c}" for c in res_df.columns
                    })
                else:
                    # Single-column result: rename it directly to the full indicator name
                    res_df = res_df.rename({res_df.columns[0]: full_name})

            # Handle the case where the plugin returned a pandas DataFrame
            else:
                # Pandas uses `.empty` to check for no rows
                if res_df.empty:
                    return None

                # If the result has multiple columns, prefix each one
                if len(res_df.columns) > 1:
                    res_df.columns = [f"{full_name}__{c}" for c in res_df.columns]
                else:
                    # Single-column result: rename it directly to the full indicator name
                    res_df.columns = [full_name]

            # Return the normalized DataFrame
            return res_df

        except Exception as e:
            # ROBUSTNESS: Catch plugin failures, log them, and return None
            # so the rest of the pipeline can continue.
            logger.error(f"Failed to execute indicator '{full_name}': {str(e)}")
            return None


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

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit to ensure threads are cleaned up."""
        self.shutdown()

    def shutdown(self):
        """Explicitly shut down the executor if it exists."""
        if self.executor:
            self.executor.shutdown(wait=True)
            self.executor = None

    def compute(
        self,
        df: Union[pd.DataFrame, pl.DataFrame],
        indicators: List[str],
        plugins: Dict[str, Any],
        disable_recursive_mapping: bool = False,
        return_polars: bool = False,
    ) -> Union[pd.DataFrame, pl.DataFrame]:
        """Compute indicators using an optimized Pandas/Polars execution strategy.

        This method routes indicator computations through the fastest possible
        execution path. Native Polars indicators are injected directly into a
        lazy execution graph, while non-Polars indicators are executed eagerly
        in parallel using a thread pool. All results are merged into a single
        output DataFrame.

        The function minimizes data copies by maintaining a shared Polars
        source and only materializing a pandas view when absolutely required.

        Args:
            df: Input data as either a pandas or Polars DataFrame.
            indicators: A list of indicator strings to compute.
            plugins: A mapping of indicator names to plugin definitions.
            disable_recursive_mapping: If True, disables nested result mapping
                and returns a flat output structure.
            return_polars: If True, return a Polars DataFrame instead of pandas.

        Returns:
            A DataFrame (pandas or Polars) containing the computed indicators.
        """
        # Detect whether the input is already a Polars DataFrame
        is_polars_input = isinstance(df, pl.DataFrame)

        # If the input is Polars, keep it zero-copy and lazy
        if is_polars_input:
            # Nothing to compute on empty input
            if df.is_empty():
                return df

            # Primary Arrow-backed data source
            df_polars_source = df

            # LazyFrame used to build the Polars execution graph
            main_pl = df.lazy()

            # Pandas view is created only if a plugin explicitly needs it
            df_for_pandas = None
        else:
            # Nothing to compute on empty input
            if df.empty:
                return df

            # Convert pandas to Polars ONCE (no rechunking to preserve zero-copy)
            df_polars_source = pl.from_pandas(df, rechunk=False)

            # Build a lazy execution graph on top of Polars
            main_pl = df_polars_source.lazy()

            # Keep a pandas copy around for legacy plugins
            df_for_pandas = df.copy()

        # Futures for threaded (pandas-style) indicator execution
        pandas_tasks = []

        # Polars expressions to be injected into the lazy graph
        polars_expressions = []

        # Process each requested indicator
        for ind_str in indicators:
            # Extract the base indicator name (before any suffixes)
            name = ind_str.split('_')[0]

            # Skip indicators that have no registered plugin
            if name not in plugins:
                continue

            # Plugin definition and resolved indicator options
            plugin_entry = plugins[name]
            ind_opts = self._resolve_options(ind_str, plugin_entry)

            # Optional metadata describing plugin capabilities
            meta_func = plugin_entry.get('meta')
            plugin_meta = meta_func() if callable(meta_func) else {}

            # FAST PATH: Native Polars execution
            if plugin_meta.get('polars', 0):
                # Polars-native calculation function
                calc_func_pl = plugin_entry.get('calculate_polars')
                if not calc_func_pl:
                    logger.warning(f"{ind_str} lacks calculate_polars, skipping.")
                    continue

                # Generate one or more Polars expressions
                expr = calc_func_pl(ind_str, ind_opts)

                # Normalize to a list and collect
                if isinstance(expr, list):
                    polars_expressions.extend(expr)
                else:
                    polars_expressions.append(expr)

            # SLOW PATH: Threaded execution using pandas or Polars DataFrame
            else:
                # Legacy or complex calculation function
                calc_func_df = plugin_entry.get('calculate')
                if not calc_func_df:
                    logger.warning(f"{ind_str} lacks calculate function, skipping.")
                    continue

                # Lazily create a thread pool executor
                if not self.executor:
                    self.executor = concurrent.futures.ThreadPoolExecutor(
                        max_workers=self.max_workers
                    )

                # Decide which DataFrame view to pass into the worker
                if plugin_meta.get('polars_input', False):
                    # Plugin can consume Polars directly (zero-copy)
                    # FiX: multithreaded locking issues. pldf not threadsafe
                    if isinstance(df_polars_source, pl.DataFrame):
                        task_input = df_polars_source.clone()
                    else:
                        # Fallback if source type is unexpected
                        task_input = df_polars_source
                else:
                    # Plugin requires pandas; convert only once if needed
                    if df_for_pandas is None:
                        df_for_pandas = df_polars_source.to_pandas()
                    task_input = df_for_pandas

                # Submit the task for parallel execution
                pandas_tasks.append(
                    self.executor.submit(
                        IndicatorWorker.execute_pandas_task,
                        df_slice=task_input,
                        p_func=calc_func_df,
                        full_name=ind_str,
                        p_opts=ind_opts
                    )
                )

        # Inject all Polars expressions into the lazy graph at once
        if polars_expressions:
            main_pl = main_pl.with_columns(polars_expressions)

        # Execute the entire Polars graph in a single materialization step
        collected_pl = main_pl.collect()

        # Assemble final output (flat or nested mapping)
        if disable_recursive_mapping:
            return self._assemble_flat(df, collected_pl, pandas_tasks, return_polars)
        else:
            return self._assemble_nested(df, collected_pl, pandas_tasks, return_polars)

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
        df_orig: Union[pd.DataFrame, pl.DataFrame]
    ) -> List[pl.DataFrame]:
        """Collect async task results and align them as Polars DataFrames.

        This function waits for a set of concurrent tasks to finish, collects
        their results, converts all outputs to Polars DataFrames, and ensures
        that every result has the same number of rows as the original input
        DataFrame. Shorter results are left-padded with null values so that
        row indices line up correctly.

        Args:
            tasks: A list of `concurrent.futures.Future` objects that return
                pandas DataFrames, Polars DataFrames, or None.
            df_orig: The original input DataFrame (pandas or Polars) used as
                the reference for how many rows each result should have.

        Returns:
            A list of Polars DataFrames, all with the same row count as
            `df_orig`, suitable for safe concatenation or downstream joins.
        """
        # This will store the final, cleaned, aligned Polars DataFrames
        aligned_results = []

        # Figure out how many rows the final outputs *must* have
        # (Polars uses `.height`, pandas uses `len()`)
        height_ref = df_orig.height if isinstance(df_orig, pl.DataFrame) else len(df_orig)

        # Loop over tasks as they finish (order is NOT guaranteed)
        for future in concurrent.futures.as_completed(tasks):
            try:
                # Get the result produced by the worker
                res_df = future.result()

                # If the task produced nothing, ignore it and move on
                if res_df is None:
                    continue

                # If the result is already Polars, keep it as-is
                # Otherwise, convert the pandas DataFrame to Polars
                if isinstance(res_df, pl.DataFrame):
                    p_res = res_df
                else:
                    p_res = pl.from_pandas(res_df)

                # If this result has fewer rows than the original input,
                # we need to pad the TOP with null rows so everything lines up
                if p_res.height < height_ref:
                    # Number of missing rows we need to add
                    pad_len = height_ref - p_res.height

                    # Create a DataFrame full of nulls that matches the schema
                    # of the result (same columns, same dtypes)
                    pad = pl.select([
                        pl.repeat(None, pad_len, dtype=dtype).alias(name)
                        for name, dtype in p_res.schema.items()
                    ])

                    # Stick the null rows on top of the actual data
                    p_res = pl.concat([pad, p_res])

                # Save the aligned result for later use
                aligned_results.append(p_res)

            except Exception as e:
                # Catch result retrieval errors to ensure robustness
                logger.error(f"Error processing future result: {str(e)}")
                continue

        # Return all aligned Polars DataFrames
        return aligned_results

    def _assemble_flat(
            self,
            df_orig: Union[pd.DataFrame, pl.DataFrame],
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

        if return_polars:
            return combined_pl

        # Convert back to Pandas only at the very end.
        # OPTIMIZATION: Use Arrow types mapper if available for speed
        return combined_pl.to_pandas(
            use_threads=True,
            types_mapper=pd.ArrowDtype if hasattr(pd, 'ArrowDtype') else None
        )

    def _assemble_nested(
        self,
        df_orig: Union[pd.DataFrame, pl.DataFrame],
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

        return result_pl.to_pandas(use_threads=True)


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
    # OPTIMIZATION: Use context manager to ensure threads are shut down
    with IndicatorEngine() as engine:
        return engine.compute(
            df,
            indicators,
            plugins,
            disable_recursive_mapping,
            return_polars
        )