import numpy as np
import pandas as pd

from util.cache import * 
from util.parallel import *


def get_data(symbol: str, timeframe:str, after_ms: int, until_ms: int, \
         limit: int = 1000, order: str = "desc", indicators: List[str] = [], \
         options: Dict = {}) -> pd.DataFrame:

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
        chunk_df = parallel_indicators(chunk_df, options, indicator_registry, disable_recursive_mapping)

    # Drop the rows before after_ms, end-limit and offset need to be done by caller
    chunk_df = chunk_df[chunk_df['sort_key'] >= after_ms]
    chunk_df = chunk_df[chunk_df['sort_key'] < until_ms]

    # Apply the limit - for multiselect via API, this is handled in API
    chunk_df = chunk_df.iloc[:limit]

    return chunk_df

    
