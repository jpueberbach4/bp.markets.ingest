#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        parallel.py
 Author:      JP Ueberbach
 Created:     2026-01-12
 Description: Provides parallel computation of technical indicators for market data.

              This module defines the `parallel_indicators` function, which:
                - Accepts market data as a pandas DataFrame.
                - Applies user-defined indicator plugins (e.g., SMA, BBANDS) in parallel
                  across symbol/timeframe slices.
                - Handles multi-column indicators and nests them in a structured
                  'indicators' dictionary per row.
                - Maintains the original dataset alongside calculated indicators.
                - Ensures correct chronological ordering and optional sorting.
                - Handles missing or NaN values gracefully.

 Requirements:
     - Python 3.8+
     - pandas
     - numpy
     - concurrent.futures

 License:
     MIT License

===============================================================================
"""

import pandas as pd
import numpy as np
import os
import concurrent.futures
from typing import List, Dict, Any

THREAD_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=os.cpu_count())
print("Using concurrency mode: thread")

def _worker_task(df_slice, p_func, full_name, p_opts):
    """Execute an indicator calculation on a DataFrame slice in a worker process.

    This helper function is intended to be executed inside a parallel worker.
    It applies a single indicator calculation function to a slice of the input
    DataFrame, normalizes the resulting column names, and returns the enriched
    DataFrame. Column prefixing is performed inside the worker to minimize
    overhead in the parent process.

    Args:
        df_slice (pd.DataFrame): A slice of the input OHLCV DataFrame to which
            the indicator should be applied.
        p_func (Callable): Indicator calculation function. This function must
            accept a DataFrame slice and an options dictionary, and return a
            Pandas DataFrame.
        full_name (str): Fully qualified indicator name (including parameters),
            used as a prefix for output column names.
        p_opts (dict): Parsed indicator options and parameters passed to the
            indicator function.

    Returns:
        Optional[pd.DataFrame]: A DataFrame containing the computed indicator
        columns with prefixed names, or ``None`` if the indicator produced no
        output.
    """
    res_df = p_func(df_slice, p_opts)
    if res_df.empty:
        return None

    # Prefix columns once in the worker to keep the main process fast
    if len(res_df.columns) > 1:
        res_df.columns = [f"{full_name}__{c}" for c in res_df.columns]
    else:
        res_df.columns = [full_name]

    return res_df


def parallel_indicators(df: pd.DataFrame, indicators: List[str], plugins: Dict[str, callable], disable_recursive_mapping: bool = False):
    """Calculates technical indicators directly on a provided DataFrame in parallel.

    This function applies user-specified indicator plugins to grouped slices of
    the DataFrame (by symbol and timeframe). Multi-column indicators are
    nested into dictionaries under a single key, and missing or NaN values
    are handled gracefully. The final DataFrame includes an 'indicators'
    column containing these nested dictionaries.

    Args:
        df (pd.DataFrame): Input DataFrame containing market data. Must include
            columns like 'symbol', 'timeframe', 'date', 'time', and optionally 'close'.
        options (Dict[str, Any]): User configuration dictionary. Expected keys:
            - 'select_data': List of selections in the form [symbol, timeframe, _, _, indicators]
            - 'order': Optional, 'asc' or 'desc' for sorting the final DataFrame
        plugins (Dict[str, callable]): Mapping of indicator names to functions that
            accept a DataFrame slice and options dictionary, returning a DataFrame.

    Returns:
        pd.DataFrame: DataFrame containing the original data and an 'indicators' column,
            where multi-column indicators are nested as dictionaries, e.g.,
            {"bbands_20_2": {"upper": val, "middle": val, "lower": val}}.

    """
    if df.empty:
        return df

    # Ensure numeric type for 'close' column if it exists
    if 'close' in df.columns:
        df['close'] = pd.to_numeric(df['close'], errors='coerce')

    # We only use one index now, sort_key
    df.set_index('sort_key', inplace=True)

    tasks = []

    for ind_str in indicators:
        parts = ind_str.split('_')
        name = parts[0]

        # Skip unknown plugins
        if name not in plugins:
            continue

        plugin_func = plugins[name].get('calculate')
        ind_opts = {}

        # Map positional arguments if plugin defines them
        if hasattr(plugin_func, "__globals__") and "position_args" in plugin_func.__globals__:
            ind_opts.update(plugin_func.__globals__["position_args"](parts[1:]))

        tasks.append(THREAD_EXECUTOR.submit(_worker_task, df_slice=df, p_func=plugin_func,
                                        full_name=ind_str, p_opts=ind_opts))

    # Collect completed results
    results = [f.result() for f in concurrent.futures.as_completed(tasks) if f.result() is not None]

    # If no results, initialize empty indicator dicts
    if not results:
        df['indicators'] = [{} for _ in range(len(df))]
        return df

    # Combine all indicator DataFrames and handle duplicate columns
    indicator_matrix = pd.concat(results, axis=1)
    indicator_matrix = indicator_matrix.loc[:, ~indicator_matrix.columns.duplicated()].copy()
    indicator_matrix = indicator_matrix.reindex(df.index)

    if disable_recursive_mapping:
        df = df.join(indicator_matrix, how='left')
    else:
        # Vectorized nesting of multi-column indicators into dictionaries
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

        # Attach nested indicators to the main DataFrame
        indicator_matrix['indicators'] = nested_list
        df = df.join(indicator_matrix[['indicators']], how='left')
        df['indicators'] = df['indicators'].apply(lambda x: x if isinstance(x, dict) else {})

    # Final reset index to restore sort_key as a column
    df = df.reset_index()
    return df

