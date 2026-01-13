"""
===============================================================================
File:        state11.py

Author:      JP Ueberbach
Created:     2026-01-12

Module for managing in-memory OHLCV data views using memory-mapped binary files.
Provides fast, zero-copy access to time-series market data and utility methods
for registering, slicing, and querying cached OHLCV datasets.

This module defines the MarketDataCache class, which:

- Maintains a registry of memory-mapped OHLCV views keyed by symbol/timeframe.
- Registers views from binary OHLCV files using NumPy structured arrays.
- Provides fast lookup of records by timestamp using binary search.
- Returns Pandas DataFrames for contiguous slices of OHLCV data.
- Caches memory-mapped files, file handles, and timestamps for efficient reuse.
- Supports runtime registration of views based on resolved query options.
- Ensures safe cleanup of existing memory maps before replacing them.

Classes:
    MarketDataCache:
        Core cache manager for OHLCV views. Handles view registration, record
        indexing, and data extraction as Pandas DataFrames.

Variables:
    cache (MarketDataCache):
        Singleton instance of MarketDataCache for global access to OHLCV views.

Key Methods:
    register_view(symbol, tf, file_path):
        Register or update a memory-mapped OHLCV view for a symbol/timeframe.

    get_chunk(symbol, tf, from_idx, to_idx):
        Retrieve a contiguous slice of OHLCV data as a Pandas DataFrame.

    get_record_count():
        Return the number of records available in a cached view.

    find_record(symbol, tf, target_ts, side="right"):
        Find the index of the closest record to a target timestamp.

    register_views_from_options(options: Dict):
        Bulk-register views from resolved runtime options in binary file mode.

Requirements:
    - Python 3.8+
    - NumPy
    - Pandas
    - FastAPI (optional for integration with API endpoints)
    - mmap (standard library)

License:
    MIT License
===============================================================================
"""


import numpy as np
import pandas as pd
import os
import mmap
from typing import Dict
from numpy.lib.stride_tricks import as_strided

# Define the C-struct equivalent for numpy
DTYPE = np.dtype([
    ('ts', '<u8'),           # Timestamp in milliseconds
    ('ohlcv', '<f8', (5,)),  # Open, High, Low, Close, Volume
    ('padding', '<u8', (2,)) # Padding to 64 bytes
])

RECORD_SIZE = 64

TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

class MarketDataCache:
    def __init__(self):
        self.mmaps = {}

    def register_view(self, symbol, tf, file_path):
        """Register or update a memory-mapped OHLCV view for a given symbol and timeframe.

        This method maps the binary OHLCV file into memory using `mmap` and
        stores metadata and structured data in the internal `mmaps` cache.
        If the file has not changed since the last registration (same size
        and modification time), the view is left unchanged. Otherwise, the
        existing memory-mapped view is replaced.

        Args:
            symbol (str): Trading symbol identifier (e.g., "EURUSD").
            tf (str): Timeframe identifier (e.g., "1m", "5m").
            file_path (str): Path to the OHLCV binary file to register.

        Returns:
            None
        """
        # Construct a unique view name based on symbol and timeframe
        view_name = f"{symbol}_{tf}"

        # Get the file size and modification time
        size = os.path.getsize(file_path)
        mtime = os.stat(file_path).st_mtime

        # Estimate number of records assuming 64 bytes per record
        num_records = size // 64

        # Check if a cached view already exists
        cached = self.mmaps.get(view_name)

        # If the cached view exists and file has not changed, do nothing
        if cached and size == cached['size'] and mtime == cached['mtime']:
            return

        # Reuse the file object if cached, otherwise open the file
        f = cached['f'] if cached else open(file_path, "rb")
        
        # Memory-map the file for fast access
        new_mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        new_mm.madvise(mmap.MADV_RANDOM)  # Optimize for random access

        # Interpret the memory-mapped bytes as a structured NumPy array
        data_view = np.frombuffer(new_mm, dtype=DTYPE)

        # Clean up old cached view if present
        if cached:
            cached['data'] = None
            cached['ts_index'] = None 
            cached['mm'].close()

        # Register the new memory-mapped view in the internal cache
        self.mmaps[view_name] = {
            'f': f, 
            'mm': new_mm, 
            'ts_index': data_view['ts'], 
            'data': data_view,
            'size': size, 
            'mtime': mtime, 
            'num_records': num_records,
            'file_path': file_path
        }


    def get_chunk(self, symbol, tf, from_idx, to_idx):
        """Retrieve a slice of cached OHLCV data as a Pandas DataFrame.

        This method extracts a contiguous range of records from the in-memory,
        memory-mapped cache for the specified symbol and timeframe. The returned
        DataFrame is normalized into columnar OHLCV form and includes derived
        time fields suitable for downstream sorting and formatting.

        Args:
            symbol (str): Trading symbol identifier (e.g., "EURUSD").
            tf (str): Timeframe identifier (e.g., "1m", "5m").
            from_idx (int): Starting index (inclusive) into the cached dataset.
            to_idx (int): Ending index (exclusive) into the cached dataset.

        Returns:
            pandas.DataFrame: A DataFrame containing OHLCV data for the requested
            index range. If the cache view does not exist, an empty DataFrame is
            returned.
        """
        # Construct the cache view name from symbol and timeframe
        view_name = f"{symbol}_{tf}"

        # Retrieve the cached dataset for this view
        cached = self.mmaps.get(view_name)

        # Return an empty DataFrame if the view is not present in cache
        if not cached:
            return pd.DataFrame()

        # Slice the structured array to the requested index range
        subset = cached['data'][from_idx:to_idx]

        # Build a normalized DataFrame from the cached OHLCV structure
        df = pd.DataFrame({
            'symbol': symbol,
            'timeframe': tf,
            'sort_key': subset['ts'],
            'open':   subset['ohlcv'][:, 0],
            'high':   subset['ohlcv'][:, 1],
            'low':    subset['ohlcv'][:, 2],
            'close':  subset['ohlcv'][:, 3],
            'volume': subset['ohlcv'][:, 4],
        })

        # Convert epoch milliseconds to timezone-aware UTC datetimes
        dt_series = pd.to_datetime(df['sort_key'], unit='ms', utc=True)

        # Extract the year component for partitioning or grouping
        df['year'] = dt_series.dt.year

        # Format the timestamp into a human-readable string
        df['time'] = dt_series.dt.strftime(TIMESTAMP_FORMAT)

        return df

    def get_record_count(self):
        """Return the number of timestamped records available in a cached view.

        This method looks up the memory-mapped cache for the current view and
        returns the total number of indexed timestamps available for lookup
        and retrieval.

        Returns:
            int: Total number of records in the cache.
        """
        # Retrieve the cached view from the memory-mapped storage
        cached = self.mmaps.get(view_name)

        # Return the number of timestamp entries in the index
        return len(cached['ts_index'])


    def find_record(self, symbol, tf, target_ts, side="right"):
        """Find the index of a record closest to a target timestamp.

        This method performs a binary search over the cached timestamp index
        using NumPy's optimized ``searchsorted`` implementation. The lookup
        returns the insertion position of ``target_ts`` based on the specified
        search side, enabling efficient range queries on time-ordered data.

        Args:
            symbol (str): Trading symbol identifier (e.g., "EURUSD").
            tf (str): Timeframe identifier (e.g., "1m", "5m").
            target_ts (int): Target timestamp in epoch milliseconds.
            side (str, optional): Search direction passed to ``np.searchsorted``.
                Use "right" to return the insertion point after existing entries,
                or "left" to return the insertion point before. Defaults to "right".

        Returns:
            int | None: Index position of the matching or insertion record if
            found, otherwise ``None``.
        """
        # Construct the cache view name from symbol and timeframe
        view_name = f"{symbol}_{tf}"

        # Retrieve the cached data for this view
        cached = self.mmaps.get(view_name)

        # Cast the target timestamp to np.uint64 (search_key is a Python object)
        # Teaching modus. It caught me completely off-guard.
        # 
        # Passing a standard Python integer forces NumPy to perform expensive "Type Promotion" 
        # and Python-object comparisons at every branch of the binary search tree. Casting to 
        # np.uint64 keeps the entire operation in high-speed C-memory, eliminating the overhead of 
        # dropping back into the Python interpreter for every comparison.
        #
        # Huge performance benefit 0.25s -> 0.05. This took me 2 hours to unravel. Just couldnt
        # understand why the profiler said that np.searchsorted took that long. Couldnt see the
        # internals of that function (the calls it performs). So it was guessing, researching.
        # Until eventually i found it. Profiling will not show you what exactly is up.
        search_key = np.uint64(target_ts)

        # Perform a binary search on the sorted timestamp index
        idx = np.searchsorted(cached['ts_index'], search_key, side=side)

        # Ensure the index is valid before returning
        if idx >= 0:
            return idx

        return None

    def register_views_from_options(self, options: Dict) -> bool:
        """Registers DuckDB views based on resolved option selections.

        This method inspects the provided options dictionary and registers
        DuckDB views for all selected data entries when operating in binary
        file mode. Each selected entry is expected to resolve to a tuple
        containing the symbol, timeframe, file path, and any modifiers.
        View registration is delegated to :meth:`register_view`.

        Args:
            options (Dict): Configuration dictionary containing runtime
                options. Must include ``'fmode'`` to indicate file mode and
                ``'select_data'`` as an iterable of resolved selection tuples.

        Returns:
            bool: ``True`` if view registration completes successfully or
            no registration is required.
        """
        # Only proceed when operating in binary file mode
        if options.get('fmode') == "binary":
            # Iterate over all selected data entries
            for item in options['select_data']:
                # Unpack the resolved selection tuple
                symbol, tf, file_path, modifiers, indicators = item
                # Register a DuckDB view for the given symbol and timeframe
                self.register_view(symbol, tf, file_path)

        return True


cache = MarketDataCache()