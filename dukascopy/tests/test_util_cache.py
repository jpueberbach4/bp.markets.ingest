#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import unittest
from unittest.mock import MagicMock, patch, mock_open
import numpy as np
import pandas as pd
import polars as pl
import mmap
import os

# Import the module
from util import cache

class TestMarketDataCache(unittest.TestCase):

    def setUp(self):
        """Reset the singleton before each test to ensure isolation."""
        cache.MarketDataCache._instance = None
        self.cache = cache.MarketDataCache()
        
        # Setup dummy data for binary testing
        # 1 record = 64 bytes (8 ts + 40 ohlcv + 16 padding)
        self.num_test_records = 10
        self.test_ts = np.arange(1000, 1000 + self.num_test_records * 100, 100, dtype='<u8')
        
        # Create a structured array matching DTYPE
        self.raw_data = np.zeros(self.num_test_records, dtype=cache.DTYPE)
        self.raw_data['ts'] = self.test_ts
        self.raw_data['ohlcv'] = np.random.rand(self.num_test_records, 5).astype('<f8')
        
        # This is the actual byte buffer that mmap would see
        self.binary_content = self.raw_data.tobytes()

    def tearDown(self):
        cache.MarketDataCache._instance = None

    @patch('util.cache.IndicatorRegistry')
    @patch('util.cache.DatasetRegistry')
    @patch('util.cache.discover_all')
    def test_singleton_behavior(self, mock_discover, mock_reg, mock_ind):
        """Verify that multiple instantiations return the same object."""
        another_cache = cache.MarketDataCache()
        self.assertIs(self.cache, another_cache)

    @patch('os.path.getsize')
    @patch('os.stat')
    @patch('builtins.open', new_callable=mock_open)
    @patch('mmap.mmap')
    def test_register_view_success(self, mock_mmap, mock_file, mock_stat, mock_getsize):
        """Tests the mmap registration and structured array mapping."""
        symbol, tf = "EUR-USD", "1m"
        file_path = "/fake/path/data.bin"
        
        mock_getsize.return_value = len(self.binary_content)
        mock_stat.return_value.st_mtime = 123456789
        
        # Create a mock object and manually attach Mock objects to the names
        # the API expects. This ensures they are trackable by assert_called_with.
        mock_mmap_obj = MagicMock()
        mock_mmap_obj.madvise = MagicMock()
        mock_mmap_obj.close = MagicMock()
        mock_mmap_obj.fileno = MagicMock(return_value=0)
        
        # Configure __len__
        mock_mmap_obj.__len__.return_value = len(self.binary_content)
        
        # Patch np.frombuffer to bypass C-buffer protocol requirements
        with patch('numpy.frombuffer') as mock_frombuffer:
            mock_frombuffer.return_value = self.raw_data
            mock_mmap.return_value = mock_mmap_obj
            
            # Execute
            self.cache._register_view(symbol, tf, file_path)
            
            # View verifications
            view_name = f"{symbol}_{tf}"
            self.assertIn(view_name, self.cache.mmaps)
            
            # Prove the code utilized the 'data' return from np.frombuffer
            self.assertEqual(self.cache.mmaps[view_name]['ts_index'][0], 1000)
            
            # Now madvise is a MagicMock instance, so this will work:
            mock_mmap_obj.madvise.assert_called_with(mmap.MADV_RANDOM)

    @patch('os.path.getsize')
    @patch('os.stat')
    def test_register_view_no_change(self, mock_stat, mock_getsize):
        """Verify that if mtime/size are same, we don't re-map (performance)."""
        view_name = "EUR-USD_1m"
        # Pre-populate cache
        self.cache.mmaps[view_name] = {
            'size': 1000, 
            'mtime': 555, 
            'f': MagicMock(), 
            'mm': MagicMock()
        }
        
        mock_getsize.return_value = 1000
        mock_stat.return_value.st_mtime = 555
        
        with patch('mmap.mmap') as mock_mmap:
            self.cache._register_view("EUR-USD", "1m", "path")
            mock_mmap.assert_not_called()

    def test_get_chunk_polars(self):
        """Tests zero-copy extraction to Polars."""
        view_name = "GBP-USD_5m"
        # Manually inject data into cache to bypass mmap for this test
        self.cache.mmaps[view_name] = {
            'data': self.raw_data,
            'ts_index': self.raw_data['ts']
        }
        
        # Get middle 5 records (idx 2 to 7)
        result = self.cache.get_chunk("GBP-USD", "5m", 2, 7, return_polars=True)
        
        self.assertIsInstance(result, pl.DataFrame)
        self.assertEqual(result.height, 5)
        self.assertEqual(result['time_ms'][0], 1200) # 1000 + 2*100
        self.assertEqual(list(result.columns), 
                         ['symbol', 'timeframe', 'time_ms', 'open', 'high', 'low', 'close', 'volume'])

    def test_get_chunk_empty(self):
        """Verify empty dataframes are returned for missing views."""
        res_pd = self.cache.get_chunk("NONEXISTENT", "1m", 0, 10, return_polars=False)
        res_pl = self.cache.get_chunk("NONEXISTENT", "1m", 0, 10, return_polars=True)
        
        self.assertTrue(isinstance(res_pd, pd.DataFrame) and res_pd.empty)
        self.assertTrue(isinstance(res_pl, pl.DataFrame) and res_pl.is_empty())

    def test_find_record_binary_search(self):
        """Verifies that find_record performs the correct np.searchsorted logic."""
        view_name = "BTC-USD_1h"
        self.cache.mmaps[view_name] = {'ts_index': self.test_ts}
        
        # Target is exactly 1200 (Index 2)
        # 'left' side: insertion before 1200 -> index 2
        idx_left = self.cache.find_record("BTC-USD", "1h", 1200, side="left")
        self.assertEqual(idx_left, 2)
        
        # Target 1250 (Between 1200 and 1300)
        # Should return index 3
        idx_mid = self.cache.find_record("BTC-USD", "1h", 1250)
        self.assertEqual(idx_mid, 3)

    def test_to_arrow_table(self):
        """Tests PyArrow conversion for high-speed inter-process transfer."""
        view_name = "ETH_1m"
        self.cache.mmaps[view_name] = {'data': self.raw_data}
        
        table = self.cache.to_arrow_table("ETH", "1m", 0, 5)
        
        import pyarrow as pa
        self.assertIsInstance(table, pa.Table)
        self.assertEqual(table.num_rows, 5)
        self.assertEqual(table.column_names, ['ts', 'open', 'high', 'low', 'close', 'volume'])

if __name__ == '__main__':
    unittest.main()