import mmap
import duckdb

class MarketDataCache:
    def __init__(self):
        # One persistent connection for the whole app
        self.con = duckdb.connect(database=":memory:")
        self.mmaps = {}  # Store (file_handle, mmap_obj)
        self.registered_views = set()

MARKETDATA_CACHE = MarketDataCache()