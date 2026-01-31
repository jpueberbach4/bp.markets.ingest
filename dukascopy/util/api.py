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

from typing import Dict,List
from util.cache import MarketDataCache
from util.parallel import parallel_indicators



def get_data_auto(
    df: pd.DataFrame,
    limit: int = -1,
    order: str = "asc",
    indicators: List[str] = []
) -> pd.DataFrame:
    """Automatically retrieve OHLCV data and indicators based on an existing DataFrame.

    This is a convenience wrapper around `get_data` that infers the symbol,
    timeframe, and time range directly from an existing OHLCV DataFrame.
    It is commonly used when re-querying or extending previously fetched data
    while preserving consistent parameters.

    The time range is derived from the first and last rows of the input
    DataFrame, and the limit defaults to the full length of the DataFrame
    unless explicitly overridden.

    Args:
        df (pd.DataFrame): Source DataFrame containing at least the columns
            `symbol`, `timeframe`, and `time_ms`. The first and last rows are
            used to infer query boundaries.
        limit (int, optional): Maximum number of rows to return. If set to -1,
            the length of the input DataFrame is used. Defaults to -1.
        order (str, optional): Sort order of the returned data ("asc" or "desc").
            Currently passed through but enforced as ascending internally.
            Defaults to "asc".
        indicators (List[str], optional): List of indicator strings to compute
            (e.g., ["sma_20", "rsi_14"]). Defaults to empty list.

    Returns:
        pd.DataFrame: A DataFrame containing OHLCV data and requested indicators
        for the inferred symbol, timeframe, and time range.
    """
    # Extract symbol and timeframe from the first row
    symbol = df.iloc[0].symbol
    timeframe = df.iloc[0].timeframe

    # Infer time boundaries from the DataFrame
    after_ms = df.iloc[0].time_ms
    until_ms = df.iloc[-1].time_ms

    # If limit is unset, default to the full DataFrame length
    if limit == -1:
        limit = len(df)

    # Delegate to the core get_data API
    # Note: until_ms is incremented to make the upper bound exclusive
    return get_data(
        symbol=symbol,
        timeframe=timeframe,
        after_ms=after_ms,
        until_ms=until_ms + 1,
        limit=limit,
        order=order,
        indicators=indicators
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
) -> pd.DataFrame:
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

    # Extend the start index backward to include warmup rows
    after_idx = after_idx - warmup_rows

    # Enforce the total row limit depending on sort order
    if until_idx - after_idx > total_limit:
        if order == "desc":
            after_idx = until_idx - total_limit
        if order == "asc":
            until_idx = after_idx + total_limit

    max_idx = cache.get_record_count(symbol, timeframe)

    # Never slice beyond last row
    if until_idx > max_idx:
        until_idx = max_idx

    # Clamp the start index to zero to avoid negative indexing
    if after_idx < 0:
        after_idx = 0

    # Skiplast handling
    if until_idx == max_idx and "skiplast" in modifiers:
        until_idx -= 1

    # Retrieve the data slice from cache
    chunk_df = cache.get_chunk(symbol, timeframe, after_idx, until_idx)

    if indicators:
        # Hot reload support (only for custom user indicators)
        indicator_registry = cache.indicators.refresh(indicators)

        # Recursive mapping disable from options, True by default since get_data API in 
        # indicators mostly needs it to be True 
        disable_recursive_mapping = options.get('disable_recursive_mapping', True)

        # Enrich the returned result with the requested indicators (parallelized)
        chunk_df = parallel_indicators(chunk_df, indicators, indicator_registry, disable_recursive_mapping)

    else:
        # When no indicators are queries, set to empty dics
        # TODO: this needs to get removed. Needs to move to HTTP API
        chunk_df['indicators'] = [{} for _ in range(len(chunk_df))]

    # Drop warmup rows
    if not chunk_df.empty and warmup_rows:
        # No need to search for after_ms and until_ms (O(N)). This was replaced with a
        # binary search (O(log N)) and ultimately reduced to an O(1) direct slice,
        # yielding a significant performance improvement.
        chunk_df = chunk_df[warmup_rows:]

    # Apply the sort
    chunk_df = chunk_df.reset_index().sort_values(by='time_ms', ascending=(order == 'asc'))

    # Reset the index to have nice 0...N indices
    chunk_df = chunk_df.reset_index(drop=True)

    # Apply the limit - for multiselect via API, this is handled in API
    chunk_df = chunk_df.iloc[:limit]

    # Drop the messy index column. Merging is happening on time_ms and optionally on symbol and tf
    chunk_df.drop(columns=['index'], errors='ignore', inplace=True)

    return chunk_df

    
