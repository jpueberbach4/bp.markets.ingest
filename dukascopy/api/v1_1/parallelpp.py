#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:         parallel.py
 Author:       JP Ueberbach
 Created:      2026-01-12
 Updated:      2026-01-15 (ProcessPoolExecutor, dynamic plugin loading)
 Description:
     Parallel execution engine for technical indicator computation.

     This module provides multiprocessing-based indicator evaluation using
     ProcessPoolExecutor to bypass the Python GIL for CPU-bound workloads.
     Indicator plugins are dynamically imported within worker processes
     to avoid pickling issues and object identity conflicts.

     Features:
       - Symbol/timeframe–scoped DataFrame slicing
       - Safe dynamic plugin loading inside worker processes
       - Parallel indicator execution across CPU cores
       - Automatic column normalization and optional recursive mapping
       - Graceful failure isolation per indicator task

     Designed for high-throughput quantitative analysis pipelines where
     indicator computation dominates runtime.
===============================================================================
"""

import pandas as pd
import numpy as np
import os
import concurrent.futures
from typing import List, Dict, Any
import sys
import importlib

sys.path.append("api/plugins/indicators")
sys.path.append("config.user/plugins/indicators")

# Switched to ProcessPoolExecutor for CPU-bound tasks
PROCESS_EXECUTOR = concurrent.futures.ProcessPoolExecutor(max_workers=os.cpu_count())
print("Using concurrency mode: process")

def _indicator_worker(df_slice, plugin_module, plugin_func_name, full_name, p_opts):
    """Executes an indicator plugin function in an isolated worker context.

    This function dynamically imports a plugin module inside the worker
    process, retrieves the specified indicator function, executes it on
    a slice of the input DataFrame, and normalizes the resulting column
    names using the provided full indicator name.

    Args:
        df_slice (pandas.DataFrame): Subset of the input DataFrame to be
            processed by the indicator function.
        plugin_module (str): Fully qualified module path containing the
            indicator plugin.
        plugin_func_name (str): Name of the indicator function to execute
            within the plugin module.
        full_name (str): Fully qualified indicator name used as a column
            prefix in the result.
        p_opts (dict): Dictionary of plugin-specific options passed to
            the indicator function.

    Returns:
        pandas.DataFrame | None: A DataFrame containing the indicator
        output with normalized column names, or None if the plugin
        returns no data or an error occurs.
    """
    try:
        # Import the plugin module dynamically within the worker process
        module = importlib.import_module(plugin_module)

        # Retrieve the indicator function from the imported module
        plugin_func = getattr(module, plugin_func_name)

        # Execute the indicator function on the provided DataFrame slice
        res_df = plugin_func(df_slice, p_opts)

        # Exit early if the plugin returned no data
        if res_df is None or res_df.empty:
            return None

        # Normalize column names using the full indicator name
        if len(res_df.columns) > 1:
            res_df.columns = [f"{full_name}__{c}" for c in res_df.columns]
        else:
            res_df.columns = [full_name]

        return {"data": res_df, "index": res_df.index}
    except Exception as e:
        # Log and suppress any worker-level exceptions
        print(f"Worker error executing {full_name}: {e}")
        return None


def parallel_indicators(
    df: pd.DataFrame,
    options: Dict[str, Any],
    plugins: Dict[str, callable],
    disable_recursive_mapping: bool = False
):
    """Computes technical indicators in parallel using multiprocessing.

    This function groups the input DataFrame by symbol and timeframe,
    executes configured indicator plugins in parallel worker processes,
    and merges the resulting indicator values back into the original
    DataFrame. Indicator outputs can optionally be mapped into a nested
    dictionary structure per row.

    Args:
        df (pandas.DataFrame): Input price or market data containing
            symbol, timeframe, and time-based columns.
        options (Dict[str, Any]): Configuration options controlling
            indicator selection, ordering, and plugin-specific parameters.
        plugins (Dict[str, callable]): Mapping of indicator names to
            callable plugin functions.
        disable_recursive_mapping (bool, optional): If True, indicator
            outputs are joined as flat columns instead of nested
            dictionaries. Defaults to False.

    Returns:
        pandas.DataFrame: The input DataFrame augmented with computed
        indicator values, sorted according to the requested order.
    """
    # Exit early if there is no data to process
    if df.empty:
        return df

    # Determine index and sorting columns based on available data
    join_keys = [k for k in ['symbol', 'timeframe', 'date', 'time'] if k in df.columns]
    temp_sort = ['date', 'time'] if 'date' in df.columns else ['time']

    # Ensure data is sorted chronologically before indicator computation
    df.sort_values(by=temp_sort, ascending=True, inplace=True)

    # Coerce close prices to numeric values if present
    if 'close' in df.columns:
        df['close'] = pd.to_numeric(df['close'], errors='coerce')

    # Set a multi-index to enable efficient symbol/timeframe slicing
    df.set_index(join_keys, inplace=True)

    tasks = []
    select_data = options.get('select_data', [])

    # Iterate over configured symbol/timeframe/indicator selections
    for symbol, timeframe, _, _, indicators in select_data:
        try:
            # Slice the DataFrame once per symbol/timeframe group
            sub_df = df.xs((symbol, timeframe), level=('symbol', 'timeframe'), drop_level=False)
        except KeyError:
            continue

        for ind_str in indicators:
            # Parse indicator name and parameters
            parts = ind_str.split('_')
            name = parts[0]

            # Skip indicators without a registered plugin
            if name not in plugins:
                continue

            plugin_func = plugins[name]

            # Extract module and function names for safe multiprocessing
            module_name = plugin_func.__module__
            func_name = plugin_func.__name__

            # Build plugin-specific options
            ind_opts = options.copy()
            if hasattr(plugin_func, "__globals__") and "position_args" in plugin_func.__globals__:
                ind_opts.update(plugin_func.__globals__["position_args"](parts[1:]))

            # Submit the indicator computation task to the process executor
            tasks.append(
                PROCESS_EXECUTOR.submit(
                    _indicator_worker,
                    df_slice=sub_df,
                    plugin_module=module_name,
                    plugin_func_name=func_name,
                    full_name=ind_str,
                    p_opts=ind_opts
                )
            )

    # Collect completed indicator results
    indicator_matrix = pd.DataFrame(index=df.index)


    results = []
    for f in concurrent.futures.as_completed(tasks):
        result = f.result()
        if result:
            # Reconstruct the worker's DataFrame
            # FORCE ALIGNMENT: Ensure it matches the master index 
            # (fixes shifts from dropna() in plugins like aroon.py)
            temp_df = result["data"].reindex(df.index)
            results.append(temp_df)

    if not results:
        df['indicators'] = [{} for _ in range(len(df))]
        is_asc = options.get('order', 'asc').lower() == 'asc'
        return df.reset_index().sort_values(by=temp_sort, ascending=is_asc)

    # Combine all indicator outputs into a single DataFrame
    indicator_matrix = pd.concat(results, axis=1)


    # Remove any duplicate indicator columns
    indicator_matrix = indicator_matrix.loc[:, ~indicator_matrix.columns.duplicated()]

    if not disable_recursive_mapping:
        # Convert flat indicator columns into nested dictionaries per row
        # Attach nested indicator dictionaries to the original DataFrame
        indicator_matrix['indicators'] = _optimize_indicator_processing_vectorized(indicator_matrix)

        df = df.join(indicator_matrix[['indicators']], how='left')
        df['indicators'] = df['indicators'].apply(
            lambda x: x if isinstance(x, dict) else {}
        )
    else:
        # Join flat indicator columns directly
        df = df.join(indicator_matrix)

    # Restore original index and ordering
    is_asc = options.get('order', 'asc').lower() == 'asc'
    return df.reset_index().sort_values(by=temp_sort, ascending=is_asc)


def _optimize_indicator_processing_vectorized(indicator_matrix):
    # Vectorized NaN detection remains on the NumPy object
    mask = ~indicator_matrix.isna().values
    columns = indicator_matrix.columns.tolist()
    
    # Pre-grouping logic (remains the same)
    grouped = {}
    regular = []
    for idx, col in enumerate(columns):
        if "__" in col:
            parts = col.split("__", 1)
            grouped.setdefault(parts[0], []).append((idx, parts[1]))
        else:
            regular.append((idx, col))
    
    # FIX: Convert to list for JSON compatibility
    values = indicator_matrix.values.tolist() 
    nested_list = []
    
    for i in range(len(values)):
        row_dict = {}
        
        # FIX: Use values[i][idx] instead of values[i, idx]
        for idx, col in regular:
            if mask[i, idx]:
                row_dict[col] = values[i][idx]
        
        for grp, indices in grouped.items():
            group_dict = {}
            has_data = False
            for idx, sub in indices:
                if mask[i, idx]:
                    group_dict[sub] = values[i][idx]
                    has_data = True
            
            if has_data:
                row_dict[grp] = group_dict
        
        nested_list.append(row_dict)
    
    return nested_list


def _shutdown():
    """Shuts down the process pool executor and terminates worker processes.

    This function gracefully stops all worker processes managed by the
    global ProcessPoolExecutor, waiting for any in-flight tasks to
    complete before releasing system resources.
    """
    # Log shutdown activity for observability and debugging
    print("Terminating worker processes.")

    # Gracefully shut down the process executor and wait for workers to exit
    PROCESS_EXECUTOR.shutdown(wait=True)
