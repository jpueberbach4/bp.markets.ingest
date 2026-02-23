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
import numpy as np
import pandas as pd
import polars as pl

from typing import Dict,List, Union
from util.cache import MarketDataCache
from util.parallel import parallel_indicators

def get_data_auto(
    df: Union[pd.DataFrame, pl.DataFrame],
    limit: int = -1,
    order: str = "asc",
    indicators: List[str] = [],
    options: Dict = {}
) -> Union[pd.DataFrame, pl.DataFrame]:
    """
    Automatically fetch OHLCV data (and optional indicators) that matches
    the time range and metadata of an existing DataFrame.

    The function inspects the input DataFrame to determine:
    - symbol
    - timeframe
    - start timestamp (after_ms)
    - end timestamp (until_ms)

    It supports both Pandas and Polars DataFrames and forwards all derived
    parameters to the core `get_data` function.

    Args:
        df: Input DataFrame containing at least the columns:
            `symbol`, `timeframe`, and `time_ms`.
            Can be either a Pandas or Polars DataFrame.
        limit: Maximum number of rows to return. If -1, defaults to the
            number of rows in the input DataFrame.
        order: Sort order of the returned data ("asc" or "desc").
        indicators: List of indicator names to compute and attach.
        options: Optional dictionary of additional parameters forwarded
            directly to `get_data`.

    Returns:
        A Pandas or Polars DataFrame (matching the backend used by `get_data`)
        containing OHLCV data and requested indicators for the inferred range.

    Note: when input options are not set, the output defaults to a pandas Dataframe.
          Generally a user should forward the incoming options to this function.
          That keeps consistency automatically.
    """

    # Check whether we're dealing with a Polars DataFrame
    is_pl = isinstance(df, pl.DataFrame)

    if is_pl:
        # Polars has no iloc; row(0) gets the first row, row(-1) gets the last
        # named=True returns a dict-like object instead of a tuple
        first_row = df.row(0, named=True)
        last_row = df.row(-1, named=True)

        # Pull required metadata from the first row
        symbol = first_row["symbol"]
        timeframe = first_row["timeframe"]

        # Use the first timestamp as the lower bound
        after_ms = first_row["time_ms"]

        # Use the last timestamp as the upper bound
        until_ms = last_row["time_ms"]

        # Total number of rows in the input DataFrame
        count = len(df)
    else:
        # Pandas path: iloc is safe regardless of index type
        symbol = df.iloc[0]["symbol"]
        timeframe = df.iloc[0]["timeframe"]
        after_ms = df.iloc[0]["time_ms"]
        until_ms = df.iloc[-1]["time_ms"]
        count = len(df)

    # If limit is -1, default to the size of the input DataFrame
    final_limit = limit if limit != -1 else count

    # Delegate the actual data retrieval to get_data
    return get_data(
        symbol=symbol,
        timeframe=timeframe,
        after_ms=int(after_ms),
        # +1 makes the upper bound exclusive so the last candle is included
        until_ms=int(until_ms) + 1,
        limit=final_limit,
        order=order,
        indicators=indicators,
        options=options
    )



def get_data(
    symbol: str,
    timeframe: str,
    after_ms: int=0,
    until_ms: int=32503680000000,
    limit: int = 1000,
    order: str = "asc",
    indicators: List[str] = [],
    options: Dict = {}
) -> Union[pd.DataFrame,pl.DataFrame]:
    """Retrieve OHLCV data for a symbol and timeframe, optionally applying indicators.

    This function fetches a contiguous slice of cached OHLCV data for a given symbol
    and timeframe, respecting time boundaries, limits, sorting order, and indicator
    warmup requirements. It also supports optional user-defined indicator calculation
    and output modifiers (e.g., skiplast).

    Args:
        symbol (str): The trading symbol to query (e.g., "EURUSD").
        timeframe (str): The OHLCV timeframe (e.g., "1m", "5m").
        after_ms (int): Inclusive lower bound timestamp in epoch milliseconds.
        until_ms (int): Exclusive upper bound timestamp in epoch milliseconds.
        limit (int, optional): Maximum number of rows to return. Defaults to 1000.
        order (str, optional): Sort order for data retrieval, "asc" or "desc".
            Defaults to "desc".
        indicators (List[str], optional): List of indicator strings to calculate
            (e.g., ["sma_20", "bbands_20_2"]). Defaults to empty list.
        options (Dict, optional): Dictionary of additional options and modifiers.
            Recognized keys include:
                - "modifiers": List of strings, e.g., ["skiplast"].
                - "disable_recursive_mapping": Boolean flag for indicator processing.

    Returns:
        pd.DataFrame: A DataFrame containing OHLCV data sliced according to the
        provided timestamps and limit, with indicator columns added if requested.
        The DataFrame includes normalized columns:
            - "symbol", "timeframe", "sort_key", "open", "high", "low",
              "close", "volume", and any indicator columns.
    """
    # Setup cache
    cache = MarketDataCache()

    # Validate inputs
    if after_ms >= until_ms:
        raise ValueError("after_ms must be less than until_ms")
    
    if limit <= 0:
        raise ValueError("limit must be positive")
    
    if order not in ["asc", "desc"]:
        raise ValueError("order must be 'asc' or 'desc'")

    # Output mode, polars or pandas (default)
    return_polars = options.get('return_polars', False)

    # Extract modifiers, eg skiplast
    modifiers = options.get('modifiers', [])

    # Check if the view is here, if not, cache it.
    cache.discover_view(symbol, timeframe)

    # Determine how many warmup rows are needed for indicators
    warmup_rows = cache.indicators.get_maximum_warmup_rows(indicators)

    # Total number of rows to retrieve, including warmup
    total_limit = limit + warmup_rows

    # Find index positions in cache for the requested time range
    after_idx = cache.find_record(symbol, timeframe, after_ms, "left")
    until_idx = cache.find_record(symbol, timeframe, until_ms, "right")

    # Store the intended start before clamping to 0
    intended_start_idx = after_idx - warmup_rows
    
    # Calculate actual index to fetch from
    effective_after_idx = max(0, intended_start_idx)
    
    # Calculate how many rows of warmup we actually managed to get.
    # If intended was -50 and we use 0, we only got (warmup_rows - 50) rows.
    actual_warmup_retrieved = warmup_rows + intended_start_idx if intended_start_idx < 0 else warmup_rows
    actual_warmup_retrieved = max(0, actual_warmup_retrieved)

    # Enforce the total row limit depending on sort order
    # Using the effective_after_idx for accurate distance calculation
    if until_idx - effective_after_idx > total_limit:
        if order == "desc":
            effective_after_idx = until_idx - total_limit
            # If we shifted the start due to limit, we are no longer at the 
            # beginning of the dataset, so we have a full warmup window again.
            actual_warmup_retrieved = warmup_rows
        if order == "asc":
            until_idx = effective_after_idx + total_limit

    max_idx = cache.get_record_count(symbol, timeframe)

    # Never slice beyond last row
    if until_idx > max_idx:
        until_idx = max_idx

    # Skiplast handling
    if until_idx == max_idx and "skiplast" in modifiers:
        until_idx -= 1

    # Retrieve the data slice from cache
    chunk_df = cache.get_chunk(symbol, timeframe, effective_after_idx, until_idx, return_polars)

    if indicators:
        # Hot reload support (only for custom user indicators)
        indicator_registry = cache.indicators.refresh(indicators)

        # Recursive mapping disable from options
        disable_recursive_mapping = options.get('disable_recursive_mapping', True)

        # Enrich the returned result with the requested indicators
        chunk_df = parallel_indicators(
            chunk_df, 
            indicators, 
            indicator_registry, 
            disable_recursive_mapping, 
            return_polars
        )

    # Drop ONLY the actual warmup rows retrieved
    is_pl = isinstance(chunk_df, pl.DataFrame)
    is_empty = chunk_df.is_empty() if is_pl else chunk_df.empty

    if not is_empty and actual_warmup_retrieved > 0:
        # Slicing by the calculated actual count, not the requested constant
        chunk_df = chunk_df.slice(actual_warmup_retrieved) if is_pl else chunk_df[actual_warmup_retrieved:]

    # Apply the sort
    force_ordering = options.get('force_ordering', False)
    if order == "desc" or force_ordering:
        if is_pl:
            chunk_df = chunk_df.sort("time_ms", descending=(order == "desc"))
        else:
            chunk_df = chunk_df.reset_index().sort_values(by='time_ms', ascending=(order == "asc"))

    # Reset/Limit/Drop (Pandas path only, Polars uses native methods)
    if is_pl:
        chunk_df = chunk_df.head(limit)
    else:
        chunk_df = chunk_df.reset_index(drop=True)
        chunk_df = chunk_df.iloc[:limit]
        chunk_df.drop(columns=['index'], errors='ignore', inplace=True)

    # Final return logic
    if return_polars and not is_pl:
        return pl.from_pandas(chunk_df)

    return chunk_df

    
