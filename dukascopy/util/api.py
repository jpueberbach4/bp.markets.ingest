#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        api.py
 Author:      JP Ueberbach
 Created:     2026-01-12
 Updated:     2026-01-23
 Description: Provides API-level data retrieval for OHLCV datasets and indicator
              computation within the Dukascopy data pipeline.

              This module defines the `get_data` function, which:
                - Retrieves time-sliced OHLCV data from the cached memory-mapped
                  datasets
                - Applies user-specified indicators, automatically handling
                  warmup rows
                - Supports output modifiers such as "skiplast" and limit constraints
                - Performs optional parallelized indicator calculations
                - Returns a normalized Pandas DataFrame with OHLCV and indicator columns

 Requirements:
     - Python 3.8+
     - NumPy
     - Pandas
     - Dukascopy memory-mapped cache and indicator infrastructure
     - Parallelization utilities (optional for indicator calculations)

 License:
     MIT License
===============================================================================
"""
import polars as pl
import traceback
import pdb

# 1. Save the original method so we can still actually execute it
_original_collect = pl.LazyFrame.collect

# 2. Define the wrapper
def debug_collect(self, *args, **kwargs):
    #print("\n>>> 🚨 COLLECT INTERCEPTED! 🚨 <<<")
    
    # Print the stack trace so you know exactly which function called this
    #traceback.print_stack(limit=20) 
    
    # OPTIONAL: Uncomment the next line to strictly pause execution here
    # pdb.set_trace() 
    
    # 3. Resume normal execution
    return _original_collect(self, *args, **kwargs)

# 4. Apply the patch
pl.LazyFrame.collect = debug_collect

import numpy as np
import pandas as pd
import polars as pl

from typing import Dict,List, Union
from util.cache import MarketDataCache
from util.parallel import parallel_indicators

def get_data_auto(
    df: Union[pd.DataFrame, pl.DataFrame, pl.LazyFrame],
    limit: int = -1,
    order: str = "asc",
    indicators: List[str] = [],
    options: Dict = {}
) -> Union[pd.DataFrame, pl.DataFrame, pl.LazyFrame]:
    """
    Automatically fetch OHLCV data matching the metadata of an existing DataFrame.
    
    BEHAVIOR:
    - Defaults to returning PANDAS DataFrame (compatibility mode).
    - Returns POLARS (LazyFrame/DataFrame) ONLY if options['return_polars'] is True.
    """

    # 1. Extract Metadata from Input (Polars Lazy, Polars Eager, or Pandas)
    if isinstance(df, pl.LazyFrame):
        # Peek at first row for start/symbol
        first_row_df = df.head(1).collect()
        if first_row_df.is_empty(): 
            return df
        
        # Peek at last row for end
        last_row_df = df.tail(1).collect()
        
        # Count rows lazily
        count = df.select(pl.len()).collect().item()
        
        first_row = first_row_df.row(0, named=True)
        last_row = last_row_df.row(0, named=True)
        
        symbol = first_row["symbol"]
        timeframe = first_row["timeframe"]
        after_ms = first_row["time_ms"]
        until_ms = last_row["time_ms"]

    elif isinstance(df, pl.DataFrame):
        if df.is_empty(): 
            return df
            
        first_row = df.row(0, named=True)
        last_row = df.row(-1, named=True)
        
        symbol = first_row["symbol"]
        timeframe = first_row["timeframe"]
        after_ms = first_row["time_ms"]
        until_ms = last_row["time_ms"]
        count = len(df)

    else:
        # Pandas Input
        if df.empty: 
            return df
            
        symbol = df.iloc[0]["symbol"]
        timeframe = df.iloc[0]["timeframe"]
        after_ms = df.iloc[0]["time_ms"]
        until_ms = df.iloc[-1]["time_ms"]
        count = len(df)

    # 2. Determine Output Type (STRICTLY based on options)
    wants_polars = options.get('return_polars', False)
    
    final_limit = limit if limit != -1 else count
    
    # Prepare options copy to inject the preference
    run_options = options.copy()
    run_options['return_polars'] = wants_polars

    # 3. Call get_data
    result = get_data(
        symbol=symbol,
        timeframe=timeframe,
        after_ms=int(after_ms),
        until_ms=int(until_ms) + 1,
        limit=final_limit,
        order=order,
        indicators=indicators,
        options=run_options
    )

    # 4. Enforce Output Consistency
    # If the user did NOT explicitly ask for Polars, ensure we give them Pandas.
    # (This handles cases where get_data defaults to Polars internally)
    if not wants_polars:
        if isinstance(result, pl.LazyFrame):
            return result.collect().to_pandas()
        elif isinstance(result, pl.DataFrame):
            return result.to_pandas()
            
    return result



def get_data(
    symbol: str,
    timeframe: str,
    after_ms: int = 0,
    until_ms: int = 32503680000000,
    limit: int = 1000,
    order: str = "asc",
    indicators: List[str] = [],
    options: Dict = {}
) -> Union[pd.DataFrame, pl.DataFrame, pl.LazyFrame]:
    """Retrieve OHLCV data for a symbol and timeframe, optionally applying indicators.
    
    Optimized for LazyFrame execution to prevent premature materialization.
    """
    # 1. Setup & Validation
    cache = MarketDataCache()
    
    if after_ms >= until_ms:
        raise ValueError("after_ms must be less than until_ms")
    
    if limit <= 0:
        raise ValueError("limit must be positive")
    
    if order not in ["asc", "desc"]:
        raise ValueError("order must be 'asc' or 'desc'")

    # Extract options
    return_polars = options.get('return_polars', False)
    modifiers = options.get('modifiers', [])
    is_lazy_requested = options.get('lazy', False)  # Check for recursion flag

    # 2. Cache Discovery & Warmup Calculation
    cache.discover_view(symbol, timeframe)
    
    warmup_rows = cache.indicators.get_maximum_warmup_rows(indicators) if indicators else 0
    total_limit = limit + warmup_rows

    # Find cache boundary indices
    after_idx = cache.find_record(symbol, timeframe, after_ms, "left")
    until_idx = cache.find_record(symbol, timeframe, until_ms, "right")

    # Adjust start index for warmup
    after_idx = after_idx - warmup_rows

    # Enforce row limits based on sort order
    if until_idx - after_idx > total_limit:
        if order == "desc":
            after_idx = until_idx - total_limit
        if order == "asc":
            until_idx = after_idx + total_limit

    # Clamp indices to valid range
    max_idx = cache.get_record_count(symbol, timeframe)
    if until_idx > max_idx: until_idx = max_idx
    if after_idx < 0: after_idx = 0
    
    # Handle 'skiplast' modifier
    if until_idx == max_idx and "skiplast" in modifiers:
        until_idx -= 1

    # 3. Retrieve Data (Potentially Lazy)
    chunk_df = cache.get_chunk(symbol, timeframe, after_idx, until_idx, return_polars)
    
    # Ensure we are working with LazyFrame for the pipeline
    is_lazy = isinstance(chunk_df, pl.LazyFrame)
    if not is_lazy and return_polars:
        chunk_df = chunk_df.lazy()
        is_lazy = True
    
    # 4. Indicator Injection (Lazy-Aware)
    if indicators:
        indicator_registry = cache.indicators.refresh(indicators)
        disable_recursive_mapping = options.get('disable_recursive_mapping', True)

        # Call parallel_indicators with lazy=True to prevent materialization
        chunk_df = parallel_indicators(
            chunk_df, 
            indicators, 
            indicator_registry, 
            disable_recursive_mapping, 
            return_polars,
            lazy=True  # Important: Pass lazy=True to support recursion
        )
        is_lazy = isinstance(chunk_df, pl.LazyFrame)

    # 5. Slicing (Warmup Drop) - FIX: Use safe integer limit
    if warmup_rows > 0:
        if is_lazy:
            # FIX: Use 2^31 - 1 (2147483647) instead of 1e12 to avoid OverflowError on u32 bindings
            SAFE_INT_MAX = 2147483647
            chunk_df = chunk_df.slice(warmup_rows, SAFE_INT_MAX)
        elif isinstance(chunk_df, pl.DataFrame):
            chunk_df = chunk_df.slice(warmup_rows)
        else:
            # Pandas
            chunk_df = chunk_df.iloc[warmup_rows:]

    # 6. Sorting
    should_sort_desc = (order == "desc")
    force_ordering = options.get('force_ordering', False)
    
    if should_sort_desc or force_ordering:
        if is_lazy or isinstance(chunk_df, pl.DataFrame):
            chunk_df = chunk_df.sort("time_ms", descending=should_sort_desc)
        else:
            chunk_df = chunk_df.sort_values(by='time_ms', ascending=not should_sort_desc)

    # 7. Limit (Head)
    if is_lazy or isinstance(chunk_df, pl.DataFrame):
        chunk_df = chunk_df.head(limit)
    else:
        chunk_df = chunk_df.head(limit)
        chunk_df.drop(columns=['index'], errors='ignore', inplace=True)

    # 8. Final Materialization (The Gatekeeper)
    # Only collect if this is the "main call" (lazy=False in options)
    if is_lazy and not is_lazy_requested:
        print("COLLECT4")
        chunk_df = chunk_df.collect()

    # Final type conversion if needed
    if return_polars and isinstance(chunk_df, pd.DataFrame):
        return pl.from_pandas(chunk_df)
    
    return chunk_df

    
