import unittest
import importlib.util
import os
import sys
from unittest.mock import patch
import pandas as pd
import polars as pl
import numpy as np

CALL_STACK = []

class TestIndicatorIntegrity(unittest.TestCase):
    def setUp(self):
        global CALL_STACK
        CALL_STACK = []

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
        if indicators is None and len(args) > 5:
            indicators = args[5]
        if indicators is None:
            indicators = []

        options = kwargs.get("options", {})

        current_active_indicators = [x[0] for x in CALL_STACK]

        for ind in indicators:
            signature = (ind, symbol, timeframe)

            if ind in current_active_indicators:
                path_str = " -> ".join([f"{i}" for i in current_active_indicators])
                raise RecursionError(
                    f"Infinite loop detected: '{ind}' calls itself!\n"
                    f"Chain: {path_str} -> {ind} (signature: {symbol}/{timeframe})"
                )

            CALL_STACK.append(signature)

            plugin_path = f"config.user/plugins/indicators/{ind}.py"
            if os.path.exists(plugin_path):
                mod_name = f"depth_{len(CALL_STACK)}_{ind}"
                if mod_name in sys.modules: del sys.modules[mod_name]

                spec = importlib.util.spec_from_file_location(mod_name, plugin_path)
                plugin = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(plugin)

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
                    pass

            CALL_STACK.pop()

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
        plugin_dir = os.path.join(os.path.dirname(__file__), '../config.user/plugins/indicators')
        if not os.path.exists(plugin_dir):
            return

        for filename in os.listdir(plugin_dir):
            if filename.endswith(".py") and not filename.startswith("__"):
                indicator_name = filename[:-3]

                with self.subTest(indicator=indicator_name):
                    with patch('util.api.get_data', side_effect=self.trace_get_data), \
                         patch('util.api.parallel_indicators', side_effect=self.sync_parallel_mock):

                        global CALL_STACK
                        CALL_STACK = [(indicator_name, "EUR-USD", "1m")]

                        file_path = os.path.join(plugin_dir, filename)
                        module_name = f"test_root_{indicator_name}"
                        if module_name in sys.modules: del sys.modules[module_name]

                        spec = importlib.util.spec_from_file_location(module_name, file_path)
                        plugin = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(plugin)

                        df = pd.DataFrame({
                            "time_ms": [1000, 2000, 3000, 4000, 5000],
                            "open": [0.8, 0.85, 0.9, 0.95, 1.0],
                            "high": [2.0, 2.1, 2.2, 2.3, 2.4],
                            "low":[0.4, 0.45, 0.5, 0.55, 0.6],
                            "close": [1.0, 1.1, 1.2, 1.3, 1.4],
                            "volume":[20.0, 25.0, 30.0, 35.0, 40.0],
                            "symbol": ["EUR-USD"] * 5,
                            "timeframe": ["1m"] * 5
                        }).astype({"time_ms": "uint64"})

                        try:
                            self._dispatch_plugin_execution(plugin, indicator_name, df)
                        except RecursionError as e:
                            self.fail(f"Infinite recursion detected in {indicator_name}!\n{e}")
                        except Exception as e:
                            self.fail(f"Indicator '{indicator_name}' crashed: {e}")

if __name__ == '__main__':
    unittest.main()
