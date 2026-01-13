import numpy as np
import pandas as pd
import os
import mmap
from typing import Dict
from numpy.lib.stride_tricks import as_strided

import ctypes

# Define the C-struct equivalent for numpy
DTYPE = np.dtype([
    ('ts', '<u8'),           # Timestamp in milliseconds
    ('ohlcv', '<f8', (5,)),  # Open, High, Low, Close, Volume
    ('padding', '<u8', (2,)) # Padding to 64 bytes
])

RECORD_SIZE = 64

class MarketDataCache:
    def __init__(self):
        self.mmaps = {}

    def register_view(self, symbol, tf, file_path):
        view_name = f"{symbol}_{tf}"
        size = os.path.getsize(file_path)
        mtime = os.stat(file_path).st_mtime
        num_records = size // 64

        cached = self.mmaps.get(view_name)

        if cached and size == cached['size'] and mtime == cached['mtime']:
            return # No changes

        f = cached['f'] if cached else open(file_path, "rb")
        
        new_mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)

        new_mm.madvise(mmap.MADV_RANDOM)
        
        # Interpret the memory-mapped bytes as a NumPy structured array
        data_view = np.frombuffer(new_mm, dtype=DTYPE)

        # Extract columns into a dictionary suitable for DataFrame creation
        data_dict = {
            "time_raw": data_view['ts'],              # Raw timestamp values
            "open": data_view['ohlcv'][:, 0],         # Open prices
            "high": data_view['ohlcv'][:, 1],         # High prices
            "low": data_view['ohlcv'][:, 2],          # Low prices
            "close": data_view['ohlcv'][:, 3],        # Close prices
            "volume": data_view['ohlcv'][:, 4]        # Trade volume
        }

        #ts_index = np.ascontiguousarray(ts_view, dtype='<u8')

        # We can now close the old one
        if cached:
            # By closing only after we have created the new one, we make sure pages remain "smoking hot"
            cached['data'] = None
            cached['ts_index'] = None 
            cached['mm'].close()

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
        view_name = f"{symbol}_{tf}"
        cached = self.mmaps.get(view_name)
        
        if not cached:
            return pd.DataFrame()

        subset = cached['data'][from_idx : to_idx]

        df = pd.DataFrame({
            'symbol': symbol,
            'timeframe': tf,
            'sort_key': subset['ts'], 
            'open':   subset['ohlcv'][:, 0],
            'high':   subset['ohlcv'][:, 1],
            'low':    subset['ohlcv'][:, 2],
            'close':  subset['ohlcv'][:, 3],
            'volume': subset['ohlcv'][:, 4]
        })

        dt_series = pd.to_datetime(df['sort_key'], unit='ms', utc=True)

        df['year'] = dt_series.dt.year.astype(str)

        fmt = "%Y-%m-%d %H:%M:%S" 
        df['time'] = dt_series.dt.strftime(fmt)

        print(df)

        return df


    def get_record_count():
        cached = self.mmaps.get(view_name)    
        return len(cached['ts_index'])

    def find_record(self, symbol, tf, target_ts, side="right"):
        view_name = f"{symbol}_{tf}"
        cached = self.mmaps.get(view_name)

        # Pulling my hair out on this PERFORMANCE fiX. 
        # Damn. I didnt understand it at all. The python cast destroys performance.
        # On lousy cast. From 0.23s to 0.05. This line. Pfff.
        search_key = np.uint64(target_ts)
        
        idx = np.searchsorted(cached['ts_index'], search_key, side=side)

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