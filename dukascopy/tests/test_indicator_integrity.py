import unittest
import importlib.util
import os
import sys
import threading
from unittest.mock import patch
import pandas as pd
import polars as pl
import numpy as np

# FIX 1: Use Thread-Local storage for the call stack.
# This ensures that if rsi-1h4h1d runs threads, they don't see each other's stack.
THREAD_DATA = threading.local()

class TestIndicatorIntegrity(unittest.TestCase):
    def setUp(self):
        # Initialize the stack for the main thread
        THREAD_DATA.stack = []

    def _get_stack(self):
        # Helper to get the stack for the current thread safely
        if not hasattr(THREAD_DATA, 'stack'):
            THREAD_DATA.stack = []
        return THREAD_DATA.stack

    def _dispatch_plugin_execution(self, plugin, indicator_name, df_pandas):
        meta = {}
        if hasattr(plugin, 'meta'):
            if callable(plugin.meta):
                meta = plugin.meta()
            elif isinstance(plugin.meta, dict):
                meta = plugin.meta
        
        args = {}
        if hasattr(plugin, 'position_args'):
            args = plugin.position_args([])

        if meta.get('polars', 0) == 1:
            if hasattr(plugin, 'calculate_polars'):
                lf = pl.from_pandas(df_pandas).lazy()
                exprs = plugin.calculate_polars(indicator_name, args)
                if not isinstance(exprs, list):
                    exprs = [exprs]
                lf.with_columns(exprs).collect()
            else:
                raise AttributeError(f"Plugin {indicator_name} has 'polars: 1' but missing 'calculate_polars'")

        elif meta.get('polars_input', 0) == 1:
            input_pl = pl.from_pandas(df_pandas)
            plugin.calculate(input_pl, args)

        else:
            plugin.calculate(df_pandas.copy(), args)

    def sync_parallel_mock(self, df, indicators, *args, **kwargs):
        """
        Mocks parallel_indicators but runs them synchronously for the test.
        """
        from util.api import get_data

        if isinstance(df, pl.DataFrame):
            symbol = df["symbol"][0]
            timeframe = df["timeframe"][0]
        elif isinstance(df, pl.LazyFrame):
            temp = df.collect()
            symbol = temp["symbol"][0]
            timeframe = temp["timeframe"][0]
        else:
            symbol = df.iloc[0].symbol
            timeframe = df.iloc[0].timeframe

        for ind_name in indicators:
            get_data(
                symbol=symbol,
                timeframe=timeframe,
                indicators=[ind_name]
            )
        return df

    def trace_get_data(self, *args, **kwargs):
        symbol = kwargs.get('symbol', args[0] if len(args) > 0 else "UNKNOWN")
        timeframe = kwargs.get('timeframe', args[1] if len(args) > 1 else "UNKNOWN")
        indicators = kwargs.get('indicators')
        options = kwargs.get("options", {})

        if indicators is None and len(args) > 5:
            indicators = args[5]
        if indicators is None:
            indicators = []

        # FIX 2: Heartbeat Bypass
        # If the plugin requests BTC-USD (the heartbeat) or just raw candles (no indicators),
        # return immediately. Do NOT run recursion checks on data fetches.
        if symbol == "BTC-USD" or not indicators:
            dummy_df = pd.DataFrame({
                "time_ms": [1000, 2000, 3000, 4000, 5000],
                "open": [100.0] * 5,
                "high": [105.0] * 5,
                "low": [95.0] * 5,
                "close": [100.0] * 5,
                "volume": [1000.0] * 5,
                "symbol": [symbol] * 5,
                "timeframe": [timeframe] * 5
            }).astype({"time_ms": "uint64"})
            
            if options.get("return_polars", False):
                 return pl.from_pandas(dummy_df).with_columns(pl.col("time_ms").cast(pl.UInt64))
            return dummy_df

        # Get thread-local stack
        current_stack = self._get_stack()
        current_active_indicators = [x[0] for x in current_stack]

        for ind in indicators:
            signature = (ind, symbol, timeframe)

            # Check for recursion within THIS thread only
            if ind in current_active_indicators:
                path_str = " -> ".join([f"{i}" for i in current_active_indicators])
                raise RecursionError(
                    f"Infinite loop detected: '{ind}' calls itself!\n"
                    f"Chain: {path_str} -> {ind} (signature: {symbol}/{timeframe})"
                )

            current_stack.append(signature)

            # Try to load from User config first, then System util
            user_plugin_path = f"config.user/plugins/indicators/{ind}.py"
            system_plugin_path = f"util/plugins/indicators/{ind}.py"
            
            plugin_path = None
            if os.path.exists(user_plugin_path):
                plugin_path = user_plugin_path
            elif os.path.exists(system_plugin_path):
                 plugin_path = system_plugin_path
            
            if plugin_path:
                mod_name = f"depth_{len(current_stack)}_{ind}"
                # Force reload to ensure clean state
                if mod_name in sys.modules: del sys.modules[mod_name]

                spec = importlib.util.spec_from_file_location(mod_name, plugin_path)
                plugin = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(plugin)

                # Create dummy data for the nested indicator
                dummy_df = pd.DataFrame({
                    "time_ms": [1000, 2000, 3000, 4000, 5000],
                    "open": [1.0, 1.1, 1.2, 1.3, 1.4],
                    "high": [1.2, 1.3, 1.4, 1.5, 1.6],
                    "low": [0.8, 0.9, 1.0, 1.1, 1.2],
                    "close": [1.1, 1.2, 1.3, 1.4, 1.5],
                    "volume": [100.0, 100.0, 100.0, 100.0, 100.0],
                    "symbol": [symbol] * 5,
                    "timeframe": [timeframe] * 5
                }).astype({"time_ms": "uint64"})

                try:
                    self._dispatch_plugin_execution(plugin, ind, dummy_df)
                except RecursionError:
                    raise
                except Exception:
                    # Ignore other errors (like calculations on dummy data), 
                    # we only care about the call graph integrity.
                    pass

            current_stack.pop()

        # Construct return data with indicator columns filled
        data = {
            "time_ms": [1000, 2000, 3000, 4000, 5000],
            "open": [1.0, 1.1, 1.2, 1.3, 1.4],
            "high": [1.2, 1.3, 1.4, 1.5, 1.6],
            "low": [0.8, 0.9, 1.0, 1.1, 1.2],
            "close": [1.1, 1.2, 1.3, 1.4, 1.5],
            "volume": [100.0, 100.0, 100.0, 100.0, 100.0],
            "symbol": [symbol] * 5,
            "timeframe": [timeframe] * 5
        }

        for ind in indicators:
            data[ind] = [50.0] * 5

        if options.get("return_polars", False):
            return pl.DataFrame(data).with_columns(pl.col("time_ms").cast(pl.UInt64))
        else:
            return pd.DataFrame(data).astype({"time_ms": "uint64"})

    def test_all_plugins_for_loops(self):
        # Scan both directories
        plugin_dirs = [
            os.path.join(os.path.dirname(__file__), '../config.user/plugins/indicators'),
            os.path.join(os.path.dirname(__file__), '../util/plugins/indicators')
        ]
        
        found_any = False
        
        for plugin_dir in plugin_dirs:
            if not os.path.exists(plugin_dir):
                continue

            for filename in os.listdir(plugin_dir):
                if filename.endswith(".py") and not filename.startswith("__"):
                    found_any = True
                    indicator_name = filename[:-3]

                    with self.subTest(indicator=indicator_name):
                        with patch('util.api.get_data', side_effect=self.trace_get_data), \
                             patch('util.api.parallel_indicators', side_effect=self.sync_parallel_mock):

                            # Reset stack for this test run
                            THREAD_DATA.stack = [(indicator_name, "EUR-USD", "1m")]

                            file_path = os.path.join(plugin_dir, filename)
                            module_name = f"test_root_{indicator_name}"
                            if module_name in sys.modules: del sys.modules[module_name]

                            spec = importlib.util.spec_from_file_location(module_name, file_path)
                            plugin = importlib.util.module_from_spec(spec)
                            spec.loader.exec_module(plugin)

                            row_count = 100
                            
                            df = pd.DataFrame({
                                "time_ms": np.arange(1000, 1000 + (row_count * 1000), 1000, dtype=np.uint64),
                                "open": np.linspace(100, 110, row_count),
                                "high": np.linspace(105, 115, row_count),
                                "low": np.linspace(95, 105, row_count),
                                "close": np.linspace(102, 112, row_count),
                                "volume": np.full(row_count, 1000.0),
                                "symbol": ["EUR-USD"] * row_count,
                                "timeframe": ["1m"] * row_count
                            })

                            try:
                                self._dispatch_plugin_execution(plugin, indicator_name, df)
                            except RecursionError as e:
                                self.fail(f"Infinite recursion detected in {indicator_name}!\n{e}")
                            except Exception as e:
                                # We fail on crashes too, as integrity tests should not crash
                                self.fail(f"Indicator '{indicator_name}' crashed: {e}")

        if not found_any:
            print("WARNING: No plugins found to test.")

if __name__ == '__main__':
    unittest.main()