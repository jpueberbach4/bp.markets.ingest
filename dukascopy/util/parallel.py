#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        parallel.py
 Author:      JP Ueberbach
 Created:     2026-01-12
 Updated:     2026-01-30

 Description:
     High-performance, hybrid-parallel execution engine for technical indicators.

     This module provides the `parallel_indicators` orchestration layer used by
     BP-Markets to compute technical indicators efficiently across large market
     datasets. It supports a mixed execution model combining:

       - Polars-native indicators for vectorized, multi-threaded execution
       - Legacy Pandas-based indicators executed concurrently via a thread pool

     The system is plugin-driven and designed to be extensible, deterministic,
     and cache-friendly. Indicator results may be returned either as flat columns
     or nested per-row dictionaries to preserve backward compatibility with
     existing consumers.

 Key Features:
     - Hybrid Pandas / Polars execution model
     - Parallel indicator computation
     - Support for multi-column indicators
     - Optional legacy dictionary nesting
     - Zero-copy alignment where possible
     - Deterministic, reproducible results

 Intended Use:
     This module is intended for data preparation and feature engineering in
     quantitative research pipelines. It is optimized for local execution and
     tight iteration loops rather than end-user-facing APIs.

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
    """Executes a single Pandas-based indicator calculation in a worker thread.

    This function runs a legacy Pandas indicator plugin, normalizes its output,
    and prefixes column names to preserve uniqueness during later merges.

    Args:
        df_slice: Input Pandas DataFrame slice (typically the full dataset).
        p_func: Indicator calculation function.
        full_name: Fully qualified indicator name (including parameters).
        p_opts: Parsed indicator options.

    Returns:
        pd.DataFrame | None: Resulting DataFrame with prefixed columns,
        or None if the indicator produced no output.
    """
    # Execute the indicator calculation
    res_df = p_func(df_slice, p_opts)
    if res_df is None or res_df.empty:
        return None

    # Prefix output columns to avoid collisions during merge
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
    """Calculates multiple technical indicators in parallel.

    This function orchestrates hybrid indicator execution using:
    - Polars for native, vectorized, multi-threaded indicators
    - Pandas + ThreadPoolExecutor for legacy plugins

    Results can either be returned as flat columns or nested dictionaries
    to maintain backward compatibility with older data consumers.

    Args:
        df: Input OHLCV Pandas DataFrame.
        indicators: List of indicator specification strings.
        plugins: Registry mapping indicator names to plugin definitions.
        disable_recursive_mapping: If True, returns a flat DataFrame instead
            of nesting indicators into per-row dictionaries.

    Returns:
        pd.DataFrame: DataFrame containing calculated indicators, either as
        flat columns or nested under the `indicators` column.
    """
    # Short-circuit for empty input
    if df.empty:
        return df

    # Ensure numeric close prices for indicator calculations
    if 'close' in df.columns:
        df['close'] = pd.to_numeric(df['close'], errors='coerce')

    # Convert to Polars for native execution and final assembly
    main_pl = pl.from_pandas(df)
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
        is_polars = plugin_meta.get('polars', False)

        # Resolve indicator arguments from positional syntax
        plugin_func = plugin_entry.get('calculate')
        ind_opts = {}
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
            # Dispatch Pandas-based indicators to the thread pool
            pandas_tasks.append(
                THREAD_EXECUTOR.submit(
                    _worker_task,
                    df_slice=df,
                    p_func=plugin_func,
                    full_name=ind_str,
                    p_opts=ind_opts
                )
            )

    t_merge_start = time.perf_counter()

    # Execute all Polars expressions in a single pass
    if polars_expressions:
        main_pl = main_pl.with_columns(polars_expressions)

    # Collect completed Pandas results
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
        # Optimized flat-column merge path
        indicator_series = []

        # Align Pandas results to full dataset length
        for res_df in pandas_results:
            for col_name in res_df.columns:
                vals = res_df[col_name].values
                if len(vals) < total_rows:
                    full_vals = np.full(total_rows, np.nan)
                    full_vals[total_rows - len(vals):] = vals
                    indicator_series.append(pl.Series(col_name, full_vals))
                else:
                    indicator_series.append(pl.Series(col_name, vals))
            del res_df

        # Force cleanup of temporary Pandas objects
        gc.collect()

        # Horizontally concatenate base data and indicator columns
        combined_pl = pl.concat(
            [main_pl] + [pl.DataFrame(indicator_series)],
            how="horizontal"
        )

        # Deduplicate columns while preserving order
        cols_to_keep = []
        visited = set()
        for c in combined_pl.columns:
            if c not in visited:
                cols_to_keep.append(c)
                visited.add(c)

        combined_pl = combined_pl.select(cols_to_keep)

        # print(f"time spend (Hybrid Merge): {time.perf_counter()-t_merge_start:.4f}s")

        return combined_pl.to_pandas(
            use_threads=True,
            types_mapper=pd.ArrowDtype if hasattr(pd, 'ArrowDtype') else None
        )

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

        # Vectorized nesting of indicators into per-row dictionaries
        records = indicator_matrix.to_dict(orient='records')
        nested_list = []

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

        # Attach nested indicator payloads to the original DataFrame
        df['indicators'] = nested_list
        return df
