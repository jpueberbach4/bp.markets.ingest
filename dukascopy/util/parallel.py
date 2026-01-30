#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        parallel.py
 Author:      JP Ueberbach
 Created:     2026-01-12
 Updated:     2026-01-30

 Description:
     High-performance, hybrid-parallel execution engine for technical indicators
     in market data. This module leverages Polars LazyFrame execution for
     vectorized, multi-threaded calculations, while supporting legacy Pandas-based
     indicator plugins via concurrent thread execution.

     Key Features:
       - Executes both Polars-native and Pandas-based indicators in parallel.
       - Supports multi-column indicators and structured nesting per row.
       - Maintains the original dataset alongside calculated indicators.
       - Optional flat-column output for performance-critical workflows.
       - Handles missing or NaN values gracefully.
       - Fully compatible with Python 3.8+ environments.

 Requirements:
     - Python 3.8+
     - pandas
     - numpy
     - polars
     - concurrent.futures (standard library)

 Usage:
     The `parallel_indicators` function is the primary interface. Pass a Pandas
     DataFrame with OHLCV data, a list of indicator strings, and a plugin registry.
     The function returns a DataFrame with calculated indicators either nested under
     an 'indicators' column or as flat columns if `disable_recursive_mapping=True`.

 License:
     MIT License
===============================================================================
"""

import pandas as pd
import numpy as np
import os
import concurrent.futures
import time
import gc
from typing import List, Dict, Any

try:
    import polars as pl
except ImportError:
    raise ImportError("Polars is required. Run 'pip install polars'")

# Shared thread pool for Pandas-based (legacy) indicator plugins
THREAD_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=os.cpu_count())


def _worker_task(df_slice, p_func, full_name, p_opts):
    """
    Executes a single Pandas-based indicator calculation inside a worker thread.

    This helper function is designed to be dispatched via a thread pool. It runs
    the indicator calculation, normalizes the output column names to avoid name
    collisions, and returns the resulting DataFrame for later merging.

    Args:
        df_slice (pd.DataFrame): Input DataFrame containing market data.
        p_func (Callable): Indicator calculation function to execute.
        full_name (str): Fully qualified indicator name (used as column prefix).
        p_opts (dict): Parsed indicator-specific options.

    Returns:
        Optional[pd.DataFrame]: A DataFrame containing the calculated indicator
        values with prefixed column names, or None if the result is empty.
    """
    # Execute the indicator calculation
    res_df = p_func(df_slice, p_opts)

    # Skip empty or invalid results
    if res_df is None or res_df.empty:
        return None

    # Prefix column names to prevent collisions during merge
    if len(res_df.columns) > 1:
        res_df.columns = [f"{full_name}__{c}" for c in res_df.columns]
    else:
        res_df.columns = [full_name]

    return res_df

def parallel_indicators(
    df: pd.DataFrame,
    indicators: List[str],
    plugins: Dict[str, Any],
    disable_recursive_mapping: bool = False
):
    """Computes technical indicators in parallel using a hybrid Pandas/Polars engine.

    This function orchestrates indicator execution using a mixed strategy:
    Polars-native indicators are executed as lazy expressions and optimized
    into a single execution plan, while legacy Pandas-based indicators are
    executed concurrently using a thread pool.

    Results can be returned either as flat indicator columns or nested per-row
    dictionaries to preserve backward compatibility with existing consumers.

    Args:
        df: Input OHLCV Pandas DataFrame.
        indicators: List of indicator specification strings.
        plugins: Registry mapping indicator names to plugin definitions.
        disable_recursive_mapping: If True, returns a flat DataFrame with
            indicator columns instead of nesting them under `indicators`.

    Returns:
        pd.DataFrame: DataFrame containing calculated indicators.
    """
    # Short-circuit for empty input
    if df.empty:
        return df

    # Ensure numeric close prices for indicator calculations
    if 'close' in df.columns:
        df['close'] = pd.to_numeric(df['close'], errors='coerce')

    # Convert to Polars LazyFrame for query optimization
    main_pl = pl.from_pandas(df, rechunk=False).lazy()
    total_rows = len(df)

    pandas_tasks = []
    polars_expressions = []

    # Parse and dispatch each indicator specification
    for ind_str in indicators:
        parts = ind_str.split('_')
        name = parts[0]

        # Skip unknown indicators
        if name not in plugins:
            continue

        plugin_entry = plugins[name]

        # Determine execution engine via plugin metadata
        meta_func = plugin_entry.get('meta')
        plugin_meta = meta_func() if callable(meta_func) else {}
        is_polars = plugin_meta.get('polars', 0)

        plugin_func = plugin_entry.get('calculate')
        ind_opts = {}

        # Resolve positional arguments from indicator string
        pos_args_func = plugin_entry.get('position_args')
        if callable(pos_args_func):
            ind_opts.update(pos_args_func(parts[1:]))
        elif hasattr(plugin_func, "__globals__") and "position_args" in plugin_func.__globals__:
            ind_opts.update(plugin_func.__globals__["position_args"](parts[1:]))

        if is_polars:
            # Route Polars-native indicators as lazy expressions
            calc_func_pl = plugin_entry.get('calculate_polars', plugin_func)
            expr = calc_func_pl(ind_str, ind_opts)
            if isinstance(expr, list):
                polars_expressions.extend(expr)
            else:
                polars_expressions.append(expr)
        else:
            # Dispatch legacy Pandas indicators to the thread pool
            pandas_tasks.append(
                THREAD_EXECUTOR.submit(
                    _worker_task,
                    df_slice=df,
                    p_func=plugin_func,
                    full_name=ind_str,
                    p_opts=ind_opts
                )
            )

    # Apply all Polars expressions to the lazy execution plan
    if polars_expressions:
        main_pl = main_pl.with_columns(polars_expressions)

    # Trigger optimized execution of the full Polars plan
    main_pl = main_pl.collect()

    # Collect completed Pandas indicator results
    pandas_results = [
        f.result()
        for f in concurrent.futures.as_completed(pandas_tasks)
        if f.result() is not None
    ]

    # Handle case where no indicators produced output
    if not pandas_results and not polars_expressions:
        df['indicators'] = [{} for _ in range(len(df))]
        return df
        
    if disable_recursive_mapping:
        indicator_frames = [main_pl]
        
        if pandas_tasks:
            # Gather all thread-pool results
            pandas_results = [f.result() for f in concurrent.futures.as_completed(pandas_tasks) if f.result() is not None]
            
            for res_df in pandas_results:
                # Schema-Safe Vectorized Padding
                p_res = pl.from_pandas(res_df)
                if len(p_res) < len(df):
                    pad_len = len(df) - len(p_res)
                    # Create a null-pad with matching schema to prevent SchemaError
                    pad = pl.DataFrame(
                        {c: [None] * pad_len for c in p_res.columns},
                        schema=p_res.schema
                    )
                    p_res = pl.concat([pad, p_res])
                indicator_frames.append(p_res)

        # Batch Merge: Multi-threaded horizontal join in Rust
        combined_pl = pl.concat(indicator_frames, how="horizontal")

        # Final Rounding: Done once in vectorized Rust (Very Fast)
        indicator_cols = [c for c in combined_pl.columns if c not in df.columns]
        combined_pl = combined_pl.with_columns([pl.col(c).round(6) for c in indicator_cols])

        # Zero-Copy Handover back to Pandas
        return combined_pl.to_pandas(use_threads=True, types_mapper=pd.ArrowDtype if hasattr(pd, 'ArrowDtype') else None)

    else:
        # Legacy nested-dictionary assembly path
        if pandas_results:
            indicator_matrix = pd.concat(pandas_results, axis=1)
            if polars_expressions:
                polars_df_as_pd = main_pl.select(
                    pl.all().exclude(df.columns)
                ).to_pandas()
                indicator_matrix = pd.concat(
                    [indicator_matrix, polars_df_as_pd],
                    axis=1
                )
        else:
            indicator_matrix = main_pl.select(
                pl.all().exclude(df.columns)
            ).to_pandas()

        # Remove duplicated indicator columns
        indicator_matrix = indicator_matrix.loc[
            :, ~indicator_matrix.columns.duplicated()
        ].copy()

        indicator_matrix = indicator_matrix.round(6)
        records = indicator_matrix.to_dict(orient='records')
        nested_list = []

        # Nest multi-column indicators into structured dictionaries
        for rec in records:
            row_dict = {}
            for k, v in rec.items():
                if pd.isna(v):
                    continue
                if "__" in k:
                    grp, sub = k.split("__", 1)
                    if grp not in row_dict:
                        row_dict[grp] = {}
                    row_dict[grp][sub] = v
                else:
                    row_dict[k] = v
            nested_list.append(row_dict)

        # Attach nested indicators to the original DataFrame
        df['indicators'] = nested_list
        return df
