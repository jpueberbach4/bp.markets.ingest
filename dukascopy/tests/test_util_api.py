#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
import polars as pl
import numpy as np
import sys
import os

try:
    from util import api
except ImportError:
    raise ImportError("Could not import 'util.api'. Ensure you run this from the project root.")

class TestMarketAPI(unittest.TestCase):

    def setUp(self):
        # Create dummy data for testing
        self.dummy_data = {
            "time_ms": np.arange(1000, 2000, 100),  # 10 rows: 1000...1900
            "open": np.random.rand(10),
            "high": np.random.rand(10),
            "low": np.random.rand(10),
            "close": np.random.rand(10),
            "volume": np.random.randint(1, 100, 10),
            "symbol": ["EURUSD"] * 10,
            "timeframe": ["1m"] * 10
        }
        self.df_pd = pd.DataFrame(self.dummy_data)
        self.df_pl = pl.DataFrame(self.dummy_data)

    @patch('util.api.MarketDataCache')
    def test_validation_errors(self, MockCache):
        """Test that invalid inputs raise appropriate ValueErrors."""
        with self.assertRaises(ValueError):
            api.get_data("EURUSD", "1m", after_ms=2000, until_ms=1000)
        
        with self.assertRaises(ValueError):
            api.get_data("EURUSD", "1m", limit=0)
            
        with self.assertRaises(ValueError):
            api.get_data("EURUSD", "1m", order="random")

    @patch('util.api.parallel_indicators')
    @patch('util.api.MarketDataCache')
    def test_get_data_basic_flow_pandas(self, MockCache, mock_parallel):
        """Test basic data retrieval returning a Pandas DataFrame."""
        mock_instance = MockCache.return_value
        mock_instance.find_record.side_effect = lambda sym, tf, ts, side: 0 if ts <= 1000 else 10
        mock_instance.get_record_count.return_value = 10
        mock_instance.get_chunk.return_value = self.df_pd.copy()
        mock_instance.indicators.get_maximum_warmup_rows.return_value = 0

        result = api.get_data("EURUSD", "1m", after_ms=0, until_ms=3000)
        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(len(result), 10)
        # Verify cache interaction
        mock_instance.discover_view.assert_called_with("EURUSD", "1m")
        mock_instance.get_chunk.assert_called()

    @patch('util.api.parallel_indicators')
    @patch('util.api.MarketDataCache')
    def test_get_data_polars_return(self, MockCache, mock_parallel):
        """Test retrieval with return_polars=True option."""
        mock_instance = MockCache.return_value
        mock_instance.find_record.side_effect = [0, 10]
        mock_instance.get_record_count.return_value = 10
        mock_instance.indicators.get_maximum_warmup_rows.return_value = 0
        mock_instance.get_chunk.return_value = self.df_pl 

        result = api.get_data("EURUSD", "1m", options={'return_polars': True})

        self.assertIsInstance(result, pl.DataFrame)
        self.assertEqual(result.height, 10)
        # Verify 5th argument (return_polars) is True
        args, _ = mock_instance.get_chunk.call_args
        self.assertTrue(args[4]) 

    @patch('util.api.parallel_indicators')
    @patch('util.api.MarketDataCache')
    def test_warmup_logic_and_indicators(self, MockCache, mock_parallel):
        """Test that warmup rows are fetched, indicators calculated, then rows dropped."""
        mock_instance = MockCache.return_value
        target_limit = 5
        warmup = 3
        
        mock_instance.indicators.get_maximum_warmup_rows.return_value = warmup
        mock_instance.find_record.side_effect = [10, 15] 
        mock_instance.get_record_count.return_value = 100
        
        # Mock getting 8 rows (3 warmup + 5 target)
        warmup_df = pd.concat([self.df_pd[:3], self.df_pd[:5]], ignore_index=True)
        mock_instance.get_chunk.return_value = warmup_df
        mock_parallel.side_effect = lambda df, *args: df

        result = api.get_data("EURUSD", "1m", limit=target_limit, indicators=["sma_3"])

        args, _ = mock_instance.get_chunk.call_args
        self.assertEqual(args[2], 7) # Start index
        
        mock_parallel.assert_called()
        self.assertEqual(len(result), 5) # Warmup stripped

    @patch('util.api.MarketDataCache')
    def test_skiplast_modifier(self, MockCache):
        """Test that skiplast modifier decrements the until_idx."""
        mock_instance = MockCache.return_value
        mock_instance.get_record_count.return_value = 100
        mock_instance.indicators.get_maximum_warmup_rows.return_value = 0
        mock_instance.find_record.side_effect = [90, 100] 
        mock_instance.get_chunk.return_value = pd.DataFrame() 

        api.get_data("EURUSD", "1m", options={'modifiers': ['skiplast']})

        # Until_idx 100 becomes 99
        args, _ = mock_instance.get_chunk.call_args
        self.assertEqual(args[3], 99)

    def test_get_data_auto(self):
        """Test the convenience wrapper infers parameters correctly."""
        with patch('util.api.get_data') as mock_get_data:
            input_df = self.df_pd.copy()
            
            api.get_data_auto(input_df, indicators=["rsi_14"])

            mock_get_data.assert_called_once()
            call_kwargs = mock_get_data.call_args[1]
            
            self.assertEqual(call_kwargs['symbol'], "EURUSD")
            self.assertEqual(call_kwargs['timeframe'], "1m")
            self.assertEqual(call_kwargs['after_ms'], 1000)
            self.assertEqual(call_kwargs['until_ms'], 1901)
            self.assertEqual(call_kwargs['limit'], 10)

    @patch('util.api.MarketDataCache')
    def test_clamping_logic(self, MockCache):
        """Test that indices do not go below zero."""
        mock_instance = MockCache.return_value
        mock_instance.get_record_count.return_value = 50
        mock_instance.indicators.get_maximum_warmup_rows.return_value = 10
        # find_record = 5. Warmup = 10. 5-10 = -5. Clamp to 0.
        mock_instance.find_record.side_effect = [5, 20]
        mock_instance.get_chunk.return_value = pd.DataFrame()

        api.get_data("EURUSD", "1m", indicators=["big_warmup"])
        
        args, _ = mock_instance.get_chunk.call_args
        self.assertEqual(args[2], 0)

    @patch('util.api.MarketDataCache')
    def test_limit_enforcement_desc(self, MockCache):
        """Test limit restricts fetch window correctly in descending order."""
        mock_instance = MockCache.return_value
        mock_instance.indicators.get_maximum_warmup_rows.return_value = 0
        mock_instance.get_record_count.return_value = 1000
        
        # Mock finding a range of 1000 records
        mock_instance.find_record.side_effect = [0, 1000]
        mock_instance.get_chunk.return_value = pd.DataFrame(columns=['time_ms', 'symbol', 'open'])

        # Execute
        api.get_data("EURUSD", "1m", limit=100, order="desc")

        # Verify that get_data calculated the correct slice indices for DESC order
        # 1000 (until) - 100 (limit) = 900 (after)
        args, _ = mock_instance.get_chunk.call_args
        self.assertEqual(args[2], 900) # after_idx
        self.assertEqual(args[3], 1000) # until_idx

if __name__ == '__main__':
    unittest.main()