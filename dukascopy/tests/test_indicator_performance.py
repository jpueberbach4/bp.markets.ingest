import unittest
import importlib.util
import os
import sys
import time
import pandas as pd
import polars as pl
import numpy as np
from typing import Dict, Any, List
from unittest.mock import MagicMock, patch

# --- DYNAMIC ABSOLUTE PATHS ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PLUGIN_DIRS = [
    os.path.join(BASE_DIR, "util/plugins/indicators"),
    os.path.join(BASE_DIR, "config.user/plugins/indicators")
]

# Threshold for warning (in milliseconds)
PERF_THRESHOLD_MS = 10

class TestAllIndicatorsPerformance(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        rows = 10000
        print(f"\n[SETUP] Generating {rows} rows of OHLCV data for performance testing...")
        
        time_ms = np.arange(1672531200000, 1672531200000 + (rows * 60000), 60000, dtype=np.uint64)
        np.random.seed(42)
        returns = np.random.normal(0, 0.001, rows)
        price_path = 100 * np.exp(np.cumsum(returns))
        
        data_dict = {
            "time_ms": time_ms,
            "open": price_path * (1 + np.random.normal(0, 0.0002, rows)),
            "high": price_path * 1.001,
            "low": price_path * 0.999,
            "close": price_path,
            "volume": np.random.randint(100, 10000, rows),
            "symbol": ["EUR-USD"] * rows,
            "timeframe": ["1m"] * rows,
            # --- FIXES FOR INTEGRATION-TEST PLUGINS (NEED TO THINK OF BETTER SOLUTION SOON) ---
            #"rsi_14": np.random.uniform(30, 70, rows), # Required by rsi-1h4h1d-org
            #"is-open": np.zeros(rows, dtype=np.int32)  # Required by rsi-1h4h1d
        }

        cls.master_pl = pl.DataFrame(data_dict)
        cls.master_pd = cls.master_pl.to_pandas()
        
        mem_usage = cls.master_pd.memory_usage(deep=True).sum() / 1024**2
        print(f"[SETUP] Data generation complete. Memory: {mem_usage:.2f} MB")
        
        header = (
            f"{'STATUS':<8} | {'INDICATOR':<25} | {'TIME (ms)':>10} | {'TYPE':<15} | {'SOURCE'}"
        )
        print("-" * len(header))
        print(header)
        print("-" * len(header))

    def _get_mock_get_data(self):
        def mock_get_data_impl(**kwargs):
            return_polars = kwargs.get('options', {}).get('return_polars', False)
            requested_indicators = kwargs.get('indicators', [])
            
            if return_polars:
                df = self.master_pl.clone()
                # Dynamically inject requested indicator columns to prevent crashes
                if requested_indicators:
                    new_cols = []
                    for ind in requested_indicators:
                        if ind not in df.columns:
                            # Generate safe dummy float data
                            dummy_data = np.random.uniform(30, 70, len(df))
                            new_cols.append(pl.Series(ind, dummy_data, dtype=pl.Float64))
                    if new_cols:
                        df = df.with_columns(new_cols)
                return df
            else:
                df = self.master_pd.copy()
                if requested_indicators:
                    for ind in requested_indicators:
                        if ind not in df.columns:
                            df[ind] = np.random.uniform(30, 70, len(df))
                return df

        return MagicMock(side_effect=mock_get_data_impl)

    def _load_plugin(self, file_path):
        module_name = f"perf_test_{os.path.basename(file_path).replace('.py', '')}"
        if module_name in sys.modules:
            del sys.modules[module_name]
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        plugin = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(plugin)
        return plugin

    def test_all_indicators_in_directories(self):
        indicator_files = []
        
        for directory in PLUGIN_DIRS:
            if os.path.exists(directory):
                for filename in os.listdir(directory):
                    if filename.endswith(".py") and not filename.startswith("__"):
                        indicator_files.append(os.path.join(directory, filename))

        if not indicator_files:
            self.fail(f"No indicator files found. Checked: {PLUGIN_DIRS}")

        indicator_files.sort()

        for file_path in indicator_files:
            indicator_name = os.path.basename(file_path).replace('.py', '')
            
            status_msg = f"TESTING  | {indicator_name:<25} ..."
            sys.stdout.write(f"\r{status_msg:<75}") 
            sys.stdout.flush()

            try:
                plugin = self._load_plugin(file_path)
                
                if hasattr(plugin, 'meta'):
                    meta = plugin.meta() if callable(plugin.meta) else plugin.meta
                else:
                    continue

                args = {}
                if hasattr(plugin, 'position_args'):
                    args = plugin.position_args(["14", "2", "9"])

                mock_get_data = self._get_mock_get_data()
                
                with patch.dict(sys.modules, {'util.api': MagicMock(get_data=mock_get_data)}):
                    if hasattr(plugin, 'get_data'):
                        plugin.get_data = mock_get_data

                    start_time = time.perf_counter()

                    if meta.get('polars', 0) == 1 and hasattr(plugin, 'calculate_polars'):
                        lf = self.master_pl.lazy()
                        exprs = plugin.calculate_polars(indicator_name, args)
                        if not isinstance(exprs, list): exprs = [exprs]
                        res = lf.with_columns(exprs).collect()

                    elif meta.get('polars_input', 0) == 1:
                        input_df = self.master_pl.clone()
                        res = plugin.calculate(input_df, args)
                        if isinstance(res, pl.LazyFrame):
                            res = res.collect()

                    else:
                        input_df = self.master_pd
                        res = plugin.calculate(input_df, args)

                    end_time = time.perf_counter()
                    duration_ms = (end_time - start_time) * 1000
                    
                    type_str = self._get_type_str(meta)
                    source_dir = "config.user" if "config.user" in file_path else "util"
                    
                    sys.stdout.write("\r" + " " * 80 + "\r")
                    
                    icon = "⚠️" if duration_ms > PERF_THRESHOLD_MS else "✅"
                    label = "SLOW" if duration_ms > PERF_THRESHOLD_MS else "OK"

                    print(f"{icon} {label:<5} | {indicator_name:<25} | {duration_ms:10.2f} | {type_str:<15} | {source_dir}")

            except Exception as e:
                sys.stdout.write("\r" + " " * 80 + "\r")
                err_msg = str(e)#.split('\n')[0][:40]
                icon, label = "❌", "FAIL"
                print(f"{icon} {label:<5} | {indicator_name:<25} | {0.0:10.2f} | ERROR           | {err_msg}")

    def _get_type_str(self, meta):
        if meta.get('polars', 0) == 1: return "Polars Expr"
        if meta.get('polars_input', 0) == 1: return "Polars DF"
        return "Pandas DF"

if __name__ == '__main__':
    for d in PLUGIN_DIRS:
        if not os.path.exists(d):
            try:
                os.makedirs(d, exist_ok=True)
            except OSError:
                pass
    unittest.main()