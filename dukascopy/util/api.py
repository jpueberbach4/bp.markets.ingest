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

from util.cache import * 
from util.parallel import *

def get_data(
    symbol: str,
    timeframe: str,
    after_ms: int,
    until_ms: int,
    limit: int = 1000,
    order: str = "desc",
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

    if len(indicators)>0:
        # Hot reload support (only for custom user indicators)
        indicator_registry = cache.indicators.refresh(indicators)

        # Recursive mapping disable from options
        disable_recursive_mapping = options.get('disable_recursive_mapping', False)

        # Enrich the returned result with the requested indicators (parallelized)
        chunk_df = parallel_indicators(chunk_df, indicators, indicator_registry, disable_recursive_mapping)

    # Drop the rows before after_ms, end-limit and offset need to be done by caller
    chunk_df = chunk_df[chunk_df['sort_key'] >= after_ms]
    chunk_df = chunk_df[chunk_df['sort_key'] < until_ms]

    # Apply the sort
    chunk_df = chunk_df.reset_index().sort_values(by='sort_key', ascending=(order == 'asc'))

    # Apply the limit - for multiselect via API, this is handled in API
    chunk_df = chunk_df.iloc[:limit]

    return chunk_df

    
