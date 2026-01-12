#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        parallel.py
 Author:      JP Ueberbach
 Created:     2026-01-07
 Description: Provides high-performance parallel execution of technical 
              analysis indicators against OHLCV datasets.

              This module leverages concurrent.futures for thread-based 
              parallelism, allowing multiple indicators (potentially across 
              different symbols and timeframes) to be calculated 
              simultaneously. It handles the complex merging logic required 
              to consolidate multi-timeframe results and nests them into 
              a JSON-compliant, sorted dictionary structure.

 Requirements:
     - Python 3.8+
     - pandas
     - numpy

 License:
     MIT License
===============================================================================
"""

import pandas as pd
import numpy as np
import concurrent.futures
from typing import List, Dict, Any

def parallel_indicators(
    data: List[Dict],
    options: Dict[str, Any],
    plugins: Dict[str, callable]
):
    """Calculates technical indicators in parallel and nests results per row.

    This function processes indicator requests defined in `options['select_data']`
    by applying indicator plugins to matching symbol/timeframe subsets of the input
    data. Indicator calculations are executed concurrently using a thread pool.
    Results are merged back into the original dataset and nested into a structured
    `indicators` dictionary per row, supporting both single- and multi-column
    indicator outputs.

    Args:
        data (List[Dict]): Raw market data records. Each record is expected to
            include at least `symbol`, `timeframe`, and time-based join keys.
        options (Dict[str, Any]): Global processing options, including
            `select_data`, ordering preferences, and plugin-specific arguments.
        plugins (Dict[str, callable]): Mapping of indicator names to callable
            plugin functions.

    Returns:
        pd.DataFrame: A DataFrame containing the original data augmented with
        a nested `indicators` column holding computed indicator values.
    """
    # Return an empty DataFrame early if there is no input data
    if not data:
        return pd.DataFrame()

    tasks = []
    select_data = options.get('select_data', [])
    
    # Execute indicator calculations concurrently
    with concurrent.futures.ThreadPoolExecutor() as executor:
        for selection in select_data:
            symbol, timeframe, _, _, indicators = selection
            
            # Filter data for the current symbol/timeframe pair
            symbol_tf_data = [
                row for row in data
                if row.get('symbol') == symbol and row.get('timeframe') == timeframe
            ]

            # Skip if no matching data exists
            if not symbol_tf_data:
                continue

            for indicator_str in indicators:
                # Parse indicator name and positional arguments
                parts = indicator_str.split('_')
                name = parts[0]
                arguments = parts[1:]

                # Skip indicators without a registered plugin
                if name not in plugins:
                    continue

                plugin_func = plugins[name]
                indicator_options = options.copy()
                
                # Map positional arguments to keyword options if supported
                if hasattr(plugin_func, "__globals__") and "position_args" in plugin_func.__globals__:
                    mapped_args = plugin_func.__globals__["position_args"](arguments)
                    indicator_options.update(mapped_args)

                # Worker function executed in a thread
                def worker(proc_data, proc_opts, full_name, p_func):
                    cols, rows = p_func(proc_data, proc_opts)
                    if not rows:
                        return None

                    df = pd.DataFrame(rows, columns=cols)
                    
                    # Identify join keys and indicator value columns
                    join_keys = [
                        c for c in ['symbol', 'timeframe', 'date', 'time']
                        if c in df.columns
                    ]
                    val_cols = [c for c in df.columns if c not in join_keys]
                    
                    # Rename indicator output columns
                    rename_map = {}
                    if len(val_cols) == 1:
                        rename_map[val_cols[0]] = full_name
                    else:
                        for vc in val_cols:
                            rename_map[vc] = f"{full_name}__{vc}"
                    
                    return df.rename(columns=rename_map)

                # Submit indicator computation task
                tasks.append(executor.submit(
                    worker, symbol_tf_data, indicator_options, indicator_str, plugin_func
                ))

    # Collect completed indicator DataFrames
    indicator_dfs = []
    for future in concurrent.futures.as_completed(tasks):
        res = future.result()
        if res is not None:
            indicator_dfs.append(res)

    final_df = pd.DataFrame(data)

    # If no indicators were computed, attach empty indicator dicts
    if not indicator_dfs:
        final_df['indicators'] = [{} for _ in range(len(final_df))]
        return final_df

    merged_cols = set()

    # Merge each indicator DataFrame into the final DataFrame
    for ind_df in indicator_dfs:
        join_keys = [
            c for c in ['symbol', 'timeframe', 'date', 'time']
            if c in ind_df.columns and c in final_df.columns
        ]
        new_cols = [c for c in ind_df.columns if c not in join_keys]
        
        for nc in new_cols:
            merged_cols.add(nc)
            if nc in final_df.columns:
                temp_df = pd.merge(
                    final_df[join_keys],
                    ind_df[[*join_keys, nc]],
                    on=join_keys,
                    how='left'
                )
                final_df[nc] = final_df[nc].fillna(temp_df[nc])
            else:
                final_df = pd.merge(
                    final_df,
                    ind_df[[*join_keys, nc]],
                    on=join_keys,
                    how='left'
                )

    # Convert flat indicator columns into nested dictionaries
    actual_indicator_cols = [c for c in merged_cols if c in final_df.columns]
    indicator_records = final_df[actual_indicator_cols].to_dict(orient='records')
    
    nested_indicators = []
    for row in indicator_records:
        row_dict = {}
        for k in sorted(row.keys()):
            val = row[k]
            if pd.isnull(val):
                continue
            
            if "__" in k:
                group_name, sub_name = k.split("__", 1)
                if group_name not in row_dict:
                    row_dict[group_name] = {}
                row_dict[group_name][sub_name] = val
            else:
                row_dict[k] = val
        nested_indicators.append(row_dict)

    # Attach nested indicators to the final DataFrame
    final_df['indicators'] = nested_indicators

    # Remove intermediate indicator columns and normalize invalid values
    final_df.drop(columns=actual_indicator_cols, inplace=True)
    final_df = final_df.replace({np.nan: None, np.inf: None, -np.inf: None})

    # Apply final sorting
    sort_cols = ['date', 'time'] if options.get('mt4') else ['time']
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by=sort_cols, ascending=is_asc)

    return final_df
