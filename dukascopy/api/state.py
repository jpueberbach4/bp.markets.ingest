#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
state.py

Author:      JP Ueberbach
Created:     2026-01-08

Module for managing in-memory OHLCV data views using DuckDB and memory-mapped
binary files. Provides efficient zero-copy access to time-series market data.

This module defines the MarketDataCache class, which:

- Maintains a persistent in-memory DuckDB connection.
- Registers DuckDB views from binary OHLCV files using NumPy memory maps.
- Caches memory-mapped files and file handles for efficient repeated access.
- Provides utility methods for registering views from runtime options.
- Handles proper cleanup of resources including memory maps and DuckDB connections.

Classes:
    MarketDataCache: Manages OHLCV data views and resource lifecycle.

Variables:
    cache (MarketDataCache): Global instance for managing market data views.

Requirements:
    - Python 3.8+
    - FastAPI
    - DuckDB
    - NumPy
    - Pandas

License:
    MIT License
===============================================================================
"""
import mmap
import weakref
import numpy as np
import pandas as pd
import duckdb
import os
from typing import Dict

# Define the C-struct equivalent for numpy
DTYPE = np.dtype([
    ('ts', '<u8'),           # Timestamp in milliseconds
    ('ohlcv', '<f8', (5,)),  # Open, High, Low, Close, Volume
    ('padding', '<u8', (2,)) # Padding to 64 bytes
])

class MarketDataCache:

    def __init__(self):
        """Initializes the instance with a DuckDB connection and internal caches.

        This constructor sets up an in-memory DuckDB connection for fast,
        ephemeral querying, and initializes internal structures to manage
        memory-mapped files and track registered DuckDB views.

        Attributes:
            con (duckdb.DuckDBPyConnection): Persistent in-memory DuckDB connection.
            mmaps (dict): Stores open file handles and their associated memory-mapped objects.
            registered_views (set): Tracks the names of DuckDB views registered by this instance.
        """
        # Create a persistent in-memory DuckDB connection for the instance
        self.con = duckdb.connect(database=":memory:")
        
        # Dictionary to store file handles and memory-mapped objects
        self.mmaps = {}
        
        # Set to keep track of registered view names
        self.registered_views = set()

        # Set the cleanup finalizer
        self._finalizer = weakref.finalize(self, self._cleanup, self.mmaps, self.con)


    def get_conn(self) -> duckdb.DuckDBPyConnection:
        """Returns the active DuckDB connection.

        This accessor provides direct access to the underlying DuckDB
        connection managed by the instance. It can be used by callers
        to execute queries or perform additional database operations.

        Returns:
            duckdb.DuckDBPyConnection: The active DuckDB connection.
        """
        return self.con

    def register_view(self, symbol: str, tf: str, file_path: str) -> bool:
        """Registers or updates a DuckDB view backed by a memory-mapped data file.

        This method creates a zero-copy DuckDB view from a binary OHLCV data file
        using a NumPy memory map. If the view already exists, it is reused unless
        the underlying file has grown, in which case the view is safely
        re-created and re-registered.

        The method maintains an internal cache of open file handles and memory
        maps to avoid unnecessary remapping and to ensure efficient access.

        Args:
            symbol (str): Trading symbol used to identify the view (e.g. "BTCUSDT").
            tf (str): Timeframe identifier used to distinguish views
                (e.g. "1m", "5m", "1h").
            file_path (str): Path to the binary data file containing structured
                OHLCV records compatible with ``DTYPE``.

        Returns:
            bool: ``True`` if the view is successfully registered or already
            up to date.
        """
        # Build a unique view name from symbol and timeframe
        view_name = f"{symbol}_{tf}_VIEW"

        # Get current file size to detect changes
        size = os.path.getsize(file_path)

        # Get current file modified time to detect changes
        mtime = os.stat(file_path).st_mtime

        # Check if this view is already memory-mapped and cached
        cached = self.mmaps.get(view_name)

        # Recreate the view if it doesn't exist or the file has grown
        if not cached or size > cached['size'] or mtime > cached['mtime']:
            if cached:
                # Re-use the file-handle
                f = cached['f']
            else:
                # Open the data file in binary read-only mode
                f = open(file_path, "rb")

            # Memory-map the entire file for zero-copy access
            mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)

            # Since this is an API, and we might query many symbols, 
            # do not trigger the kernel to preload too much
            mm.madvise(mmap.MADV_RANDOM) 

            # Interpret the memory-mapped bytes as a NumPy structured array
            data_view = np.frombuffer(mm, dtype=DTYPE)

            # Extract columns into a dictionary suitable for DataFrame creation
            data_dict = {
                "time_raw": data_view['ts'],              # Raw timestamp values
                "open": data_view['ohlcv'][:, 0],         # Open prices
                "high": data_view['ohlcv'][:, 1],         # High prices
                "low": data_view['ohlcv'][:, 2],          # Low prices
                "close": data_view['ohlcv'][:, 3],        # Close prices
                "volume": data_view['ohlcv'][:, 4]        # Trade volume
            }

            # Unregister the old view in DuckDB
            if cached: self.con.unregister(view_name)

            # Register the data dictionary as a view in DuckDB
            self.con.register(view_name, data_dict)

            # Close the old memory map
            if cached: cached['mm'].close()

            # Cache the file handle, memory map, and size for future reuse
            self.mmaps[view_name] = {'f': f, 'mm': mm, 'size': size, 'mtime': mtime}

            # Track registered view names
            self.registered_views.add(view_name)
            

        # Indicate successful registration (or no-op if unchanged)
        return True


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
                symbol, tf, file_path, modifiers = item
                # Register a DuckDB view for the given symbol and timeframe
                self.register_view(symbol, tf, file_path)

        return True

    @staticmethod
    def _cleanup(mmaps: Dict, con: duckdb.DuckDBPyConnection):
        """Releases all resources in mmaps and close DuckDB.

        This method cleans up open memory-mapped files and their associated
        file handles, then closes the active DuckDB connection. It should be
        called during shutdown or when the instance is no longer needed to
        ensure that system resources are properly released.

        Returns:
            None
        """
        # Iterate over all cached file handles and memory maps
        for entry in mmaps.values():
            try:
                # Close the memory-mapped region
                entry['mm'].close()
                # Close the associated file handle
                entry['f'].close()
            except Exception:
                pass
        
        # Clear the memory maps Dictionary
        mmaps.clear()
        # Close the DuckDB connection
        con.close()

# Setup a global state cache
cache = MarketDataCache()