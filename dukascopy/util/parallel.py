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

    # Determine multi-index keys for symbol, timeframe, date, time
    join_keys = [k for k in ['symbol', 'timeframe', 'date', 'time'] if k in df.columns]

    # Ensure numeric type for 'close' column if it exists
    if 'close' in df.columns:
        df['close'] = pd.to_numeric(df['close'], errors='coerce')

    # Set multi-index for efficient slicing by symbol/timeframe
    df.set_index(join_keys, inplace=True)

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

        def worker(df_slice, p_func, full_name, p_opts):
            res_df = p_func(df_slice, p_opts)
            if res_df.empty:
                return None

            # Prefix multi-column results with '__', single-column gets full name
            if len(res_df.columns) > 1:
                res_df.columns = [f"{full_name}__{c}" for c in res_df.columns]
            else:
                res_df.columns = [full_name]

            return res_df

        tasks.append(THREAD_EXECUTOR.submit(worker, df_slice=df, p_func=plugin_func,
                                        full_name=ind_str, p_opts=ind_opts))

    # Collect completed results
    results = [f.result() for f in concurrent.futures.as_completed(tasks) if f.result() is not None]

    # If no results, initialize empty indicator dicts
    if not results:
        df['indicators'] = [{} for _ in range(len(df))]
        return df

    # Combine all indicator DataFrames and handle duplicate columns
    indicator_matrix = pd.concat(results, axis=1)
    indicator_matrix = indicator_matrix.groupby(level=0, axis=1).first()

    if not disable_recursive_mapping:
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
    else:
        df = df.join(indicator_matrix)

    return df

