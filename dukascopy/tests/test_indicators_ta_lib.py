import unittest
import importlib.util
import os
import pandas as pd
import numpy as np
import polars as pl
from typing import Dict, Any

try:
    import talib
    HAS_TALIB = True
except ImportError:
    HAS_TALIB = False

# Mapping of your local filename to the TA-Lib function name
TALIB_MAP = {
    "sma": "SMA", "ema": "EMA", "bbands": "BBANDS", "rsi": "RSI",
    "macd": "MACD", "atr": "ATR", "adx": "ADX", "stddev": "STDDEV",
    "cci": "CCI", "obv": "OBV", "cmo": "CMO", "mfi": "MFI", 
    "aroon": "AROON", "roc": "ROC", "adl": "AD", "chaikin": "ADOSC",
    "psar": "SAR", "stochastic": "STOCH", "williamsr": "WILLR",
    "uo": "ULTOSC", "midpoint": "MIDPOINT", "atrp": "NATR", 
    "eom": "EMV"
}

@unittest.skipIf(not HAS_TALIB, "TA-Lib not installed. Skipping equivalence tests.")
class TestIndicatorEquivalence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        np.random.seed(42)
        size = 2500
        returns = np.random.normal(0.0001, 0.01, size)
        close = 100 * np.exp(np.cumsum(returns))
        vol = np.random.uniform(0.001, 0.005, size)
        high = close * (1 + vol)
        low = close * (1 - vol)
        open_price = close * (1 + np.random.uniform(-0.002, 0.002, size))
        
        cls.data = {
            "open": open_price,
            "high": np.maximum(high, np.maximum(open_price, close)),
            "low": np.minimum(low, np.minimum(open_price, close)),
            "close": close,
            "volume": np.random.uniform(1000, 5000, size)
        }
        cls.df_pd = pd.DataFrame(cls.data)
        cls.df_pl = pl.DataFrame(cls.data)

    def get_talib_ref(self, name: str, df: pd.DataFrame, options: Dict[str, Any]):
        func = getattr(talib, name.upper(), None)
        if not func: return None

        # Logic to route parameters correctly to TA-Lib
        if name.upper() in ["SMA", "EMA", "RSI", "STDDEV", "CMO", "ROC"]:
            return func(df["close"].values, timeperiod=int(options.get('period', 14)))
        elif name.upper() == "BBANDS":
            p = int(options.get('period', 20))
            std = float(options.get('std', 2.0))
            return func(df["close"].values, timeperiod=p, nbdevup=std, nbdevdn=std, matype=0)
        elif name.upper() == "MACD":
            return func(df["close"].values, 12, 26, 9)
        elif name.upper() in ["ATR", "ADX", "CCI", "NATR"]:
            p = int(options.get('period', 14))
            return func(df["high"].values, df["low"].values, df["close"].values, timeperiod=p)
        elif name.upper() == "MFI":
            return func(df["high"].values, df["low"].values, df["close"].values, df["volume"].values, timeperiod=int(options.get('period', 14)))
        elif name.upper() == "OBV":
            return func(df["close"].values, df["volume"].values)
        elif name.upper() == "AROON":
            return func(df["high"].values, df["low"].values, timeperiod=int(options.get('period', 14)))
        elif name.upper() == "SAR":
            s = float(options.get('step', 0.02))
            m = float(options.get('max_step', 0.2))
            return func(df["high"].values, df["low"].values, acceleration=s, maximum=m)
        elif name.upper() == "WILLR":
            return func(df["high"].values, df["low"].values, df["close"].values, timeperiod=int(options.get('period', 14)))
        elif name.upper() == "ULTOSC":
            return func(df["high"].values, df["low"].values, df["close"].values, 
                        timeperiod1=int(options.get('p1', 7)), 
                        timeperiod2=int(options.get('p2', 14)), 
                        timeperiod3=int(options.get('p3', 28)))
        elif name.upper() == "STOCH":
            return func(df["high"].values, df["low"].values, df["close"].values, 
                        fastk_period=int(options.get('k_period', 5)), 
                        slowk_period=int(options.get('sk_period', 3)), slowk_matype=0, 
                        slowd_period=int(options.get('sd_period', 3)), slowd_matype=0)
        elif name.upper() == "AD":
            return func(df["high"].values, df["low"].values, df["close"].values, df["volume"].values)
        elif name.upper() == "ADOSC":
            return func(df["high"].values, df["low"].values, df["close"].values, df["volume"].values, fastperiod=3, slowperiod=10)
        elif name.upper() == "MIDPOINT":
            return func(df["close"].values, timeperiod=int(options.get('period', 14)))
        elif name.upper() == "EMV":
            # TA-Lib doesn't have a native EOM/EMV, typically you'd skip or use a custom check
            return None

        return None

    def test_indicators_against_talib(self):
        plugin_dir = "util/plugins/indicators"
        files = sorted([f for f in os.listdir(plugin_dir) if f.endswith(".py")])

        for filename in files:
            indicator_name = filename[:-3]
            if indicator_name not in TALIB_MAP: continue
            talib_func_name = TALIB_MAP[indicator_name]
            
            with self.subTest(indicator=indicator_name):
                spec = importlib.util.spec_from_file_location(indicator_name, os.path.join(plugin_dir, filename))
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                options = module.position_args([])
                expected = self.get_talib_ref(talib_func_name, self.df_pd, options)
                if expected is None: continue 

                meta = module.meta()
                use_polars = meta.get("polars", 1) == 1
                warmup = 300 

                print(f"testing indicator {indicator_name}...")

                if use_polars and hasattr(module, "calculate_polars"):
                    # --- POLARS EXPRESSION PATH ---
                    expr = module.calculate_polars(indicator_name, options)
                    exprs = expr if isinstance(expr, list) else [expr]
                    res_pl = self.df_pl.select(exprs)
                    
                    if isinstance(expected, tuple):
                        suffixes = [
                            "__upper", "__mid", "__lower", "__macd", "__signal", "__hist", 
                            "__aroon_down", "__aroon_up", "__stoch_k", "__stoch_d",
                            "__adx", "__plus_di", "__minus_di"
                        ]
                        found_cols = [s for s in suffixes if f"{indicator_name}{s}" in res_pl.columns]
                        
                        for i, s in enumerate(found_cols):
                            actual = res_pl[f"{indicator_name}{s}"].to_numpy()
                            if i < len(expected):
                                np.testing.assert_allclose(actual[warmup:], expected[i][warmup:], atol=1e-8, equal_nan=True)
                    else:
                        actual = res_pl[indicator_name].to_numpy() if indicator_name in res_pl.columns else res_pl.to_numpy()[:, 0]
                        np.testing.assert_allclose(actual[warmup:], expected[warmup:], atol=1e-8, equal_nan=True)
                else:
                    # --- CALCULATE (DATAFRAME) PATH ---
                    if meta.get('polars_input', 0) == 1:
                        input_data = pl.from_pandas(self.df_pd)
                    else:
                        input_data = self.df_pd

                    res = module.calculate(input_data, options)
                    
                    # Handle Polars DataFrame/LazyFrame returns
                    if isinstance(res, (pl.DataFrame, pl.LazyFrame)):
                        if isinstance(res, pl.LazyFrame):
                            res = res.collect()
                        
                        if isinstance(expected, tuple):
                            for i in range(min(res.width, len(expected))):
                                actual = res.to_numpy()[:, i]
                                exp_segment = expected[i][-len(actual):]
                                dropped = len(expected[i]) - len(actual)
                                test_slice = max(0, warmup - dropped)
                                np.testing.assert_allclose(actual[test_slice:], exp_segment[test_slice:], atol=1e-8, equal_nan=True)
                        else:
                            actual = res.to_numpy()[:, 0]
                            exp_segment = expected[-len(actual):]
                            dropped = len(expected) - len(actual)
                            test_slice = max(0, warmup - dropped)
                            np.testing.assert_allclose(actual[test_slice:], exp_segment[test_slice:], atol=1e-8, equal_nan=True)
                    else:
                        # Handle standard Pandas/Numpy returns
                        res_pd = res
                        if isinstance(expected, tuple):
                            for i in range(min(res_pd.shape[1], len(expected))):
                                actual = res_pd.iloc[:, i].to_numpy()
                                exp_segment = expected[i][-len(actual):]
                                dropped = len(expected[i]) - len(actual)
                                test_slice = max(0, warmup - dropped)
                                np.testing.assert_allclose(actual[test_slice:], exp_segment[test_slice:], atol=1e-8, equal_nan=True)
                        else:
                            actual = res_pd.iloc[:, 0].to_numpy() if hasattr(res_pd, 'iloc') else res_pd
                            exp_segment = expected[-len(actual):]
                            dropped = len(expected) - len(actual)
                            test_slice = max(0, warmup - dropped)
                            np.testing.assert_allclose(actual[test_slice:], exp_segment[test_slice:], atol=1e-8, equal_nan=True)