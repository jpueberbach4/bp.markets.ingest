"""
===============================================================================
File:        cache.py

Author:      JP Ueberbach
Created:     2026-01-12
Updated:     2026-01-23

In-memory cache and view manager for OHLCV market data backed by
memory-mapped binary files.

This module provides fast, zero-copy access to time-series OHLCV data
stored in fixed-width binary files. It manages the lifecycle of
memory-mapped views keyed by symbol and timeframe, supports efficient
timestamp-based lookups via binary search, and exposes utilities for
extracting contiguous data slices as normalized Pandas DataFrames.

The primary entry point is the `MarketDataCache` class, which integrates
with the dataset discovery layer and indicator registry to dynamically
register views at runtime based on resolved query options.

Key capabilities:
    - Maintain a registry of memory-mapped OHLCV views by symbol/timeframe.
    - Register and refresh views from binary OHLCV files using NumPy
      structured arrays.
    - Detect file changes and safely replace stale memory maps.
    - Perform fast timestamp lookups using `np.searchsorted`.
    - Extract contiguous OHLCV slices as Pandas DataFrames.
    - Lazily register views on demand via dataset discovery.
    - Share memory-mapped files across queries for efficient reuse.

Design notes:
    - Binary files are assumed to use a fixed 64-byte record layout.
    - Data access is read-only and optimized for random access.
    - Memory maps are reused when file size and modification time
      are unchanged.
    - Timestamp indices are stored as NumPy arrays for efficient search.
    - Indicator execution is handled externally; this module provides
      only the underlying OHLCV data views.

Classes:
    MarketDataCache:
        Core cache manager responsible for view registration, memory-map
        lifecycle management, record indexing, and data extraction.

Module-level objects:
    cache (MarketDataCache):
        Singleton cache instance used by downstream query and API layers.

Requirements:
    - Python 3.8+
    - NumPy
    - Pandas
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
from util.helper import *
from util.registry import *
from util.indicator import *

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
        # Discover datasets and build registry
        self.registry = DatasetRegistry(discover_all())
        # Discover indicators and build registry
        self.indicators = IndicatorRegistry()

    def discover_view(self, symbol, tf):
        """Discover and register a dataset view for a symbol and timeframe.

        This method looks up a dataset matching the given symbol and timeframe
        from the registry and registers a view backed by the dataset's file
        path. If no matching dataset exists, an exception is raised.

        Args:
            symbol (str): Trading symbol identifier (e.g., "EURUSD").
            tf (str): Timeframe identifier (e.g., "5m", "1h").

        Raises:
            Exception: If no dataset is found for the given symbol and timeframe.
        """
        # Look up the dataset matching the symbol and timeframe
        dataset = self.registry.find(symbol, tf)

        # Fail fast if no dataset is available
        if not dataset:
            raise Exception(f"No dataset found for symbol {symbol}/{tf}")

        # Register a view using the dataset's file path
        self._register_view(symbol, tf, dataset.path)


    def _register_view(self, symbol, tf, file_path):
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

        # TODO: move this to generate_output, only support for output types that require it
        # Convert epoch milliseconds to timezone-aware UTC datetimes
        dt_series = pd.to_datetime(df['sort_key'], unit='ms', utc=True)

        # Extract the year component for partitioning or grouping
        df['year'] = dt_series.dt.year

        # Format the timestamp into a human-readable string
        df['time'] = dt_series.dt.strftime(TIMESTAMP_FORMAT)

        return df

    def get_record_count(self, symbol, tf):
        """Return the number of timestamped records available in a cached view.

        This method looks up the memory-mapped cache for the current view and
        returns the total number of indexed timestamps available for lookup
        and retrieval.

        Returns:
            int: Total number of records in the cache.
        """
        # Construct the cache view name from symbol and timeframe
        view_name = f"{symbol}_{tf}"
        
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

        # Cast to numpy uint64 to avoid re-entry to GIL on each search
        search_key = np.uint64(target_ts)

        # Perform a binary search on the sorted timestamp index
        idx = np.searchsorted(cached['ts_index'], search_key, side=side)

        # Ensure the index is valid before returning
        if idx >= 0:
            return idx

        return None

cache = MarketDataCache()