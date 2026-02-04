import unittest
import importlib.util
import os
import pandas as pd
import numpy as np
import polars as pl
from typing import Dict, Any

"""
This test is mainly to check the system indicators against a very old but industry standard TA-lib.

If you have the TA-lib installed-it can be difficult to install it-then this test will run.
The test is normally only to be performed by a system developer. For normal users its no use.

Except for those that really really want to validate.
"""
try:
    import talib
    HAS_TALIB = True
except ImportError:
    HAS_TALIB = False

TALIB_MAP = {
    "sma": "SMA", 
    "ema": "EMA", 
    "bbands": "BBANDS", 
    "rsi": "RSI",
    "macd": "MACD", 
    "atr": "ATR", 
    "adx": "ADX", 
    "stddev": "STDDEV",
    "cci": "CCI", 
    "obv": "OBV", 
    "cmo": "CMO", 
    "mfi": "MFI", 
    "aroon": "AROON", 
    "roc": "ROC",
    "adl": "AD",
    "chaikin": "ADOSC",
    "psar": "SAR",
    "stochastic": "STOCH",
    "williamsr": "WILLR",
    "uo": "ULTOSC",
    "midpoint": "MIDPOINT",
    "httrendline": "HT_TRENDLINE"
}

# Add the skip decorator to the entire class
@unittest.skipIf(not HAS_TALIB, "TA-Lib not installed. Skipping equivalence tests.")
class TestIndicatorEquivalence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """
        Generates logically consistent OHLC data.
        High >= Open/Close >= Low.
        """
        np.random.seed(42)
        size = 2500
        
        # Generate a realistic price walk (Geometric Brownian Motion)
        returns = np.random.normal(0.0001, 0.01, size)
        close = 100 * np.exp(np.cumsum(returns))
        
        # Generate OHLC with logical constraints
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
        # This is safe because the class is skipped if HAS_TALIB is False
        func = getattr(talib, name.upper(), None)
        if not func: return None
        p = int(options.get('period', 14))
        
        if name.upper() in ["SMA", "EMA", "RSI", "STDDEV", "CMO", "ROC"]:
            return func(df["close"].values, timeperiod=p)
        elif name.upper() == "BBANDS":
            std = float(options.get('std', 2.0))
            return func(df["close"].values, timeperiod=p, nbdevup=std, nbdevdn=std, matype=0)
        elif name.upper() == "MACD":
            return func(df["close"].values, 12, 26, 9)
        elif name.upper() in ["ATR", "ADX", "CCI"]:
            return func(df["high"].values, df["low"].values, df["close"].values, timeperiod=p)
        elif name.upper() == "MFI":
            return func(df["high"].values, df["low"].values, df["close"].values, df["volume"].values, timeperiod=p)
        elif name.upper() == "OBV":
            return func(df["close"].values, df["volume"].values)
        elif name.upper() == "AROON":
            return func(df["high"].values, df["low"].values, timeperiod=p)

        # New ones
        elif name.upper() == "SAR":
            return func(df["high"].values, df["low"].values, acceleration=0.02, maximum=0.2)
        elif name.upper() == "WILLR":
            return func(df["high"].values, df["low"].values, df["close"].values, timeperiod=p)
        elif name.upper() == "ULTOSC":
            return func(df["high"].values, df["low"].values, df["close"].values, timeperiod1=7, timeperiod2=14, timeperiod3=28)
        elif name.upper() == "STOCH":
            return func(df["high"].values, df["low"].values, df["close"].values, 
                        fastk_period=5, slowk_period=3, slowk_matype=0, slowd_period=3, slowd_matype=0)
        elif name.upper() == "AD":
            return func(df["high"].values, df["low"].values, df["close"].values, df["volume"].values)
        elif name.upper() == "ADOSC":
            return func(df["high"].values, df["low"].values, df["close"].values, df["volume"].values, fastperiod=3, slowperiod=10)

        return None

    def test_indicators_against_talib(self):
        plugin_dir = "util/plugins/indicators"
        files = sorted([f for f in os.listdir(plugin_dir) if f.endswith(".py")])

        for filename in files:
            indicator_name = filename[:-3]
            talib_func_name = TALIB_MAP.get(indicator_name, indicator_name.upper())
            
            with self.subTest(indicator=indicator_name):
                spec = importlib.util.spec_from_file_location(indicator_name, os.path.join(plugin_dir, filename))
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                options = module.position_args([])
                p = int(options.get('period', 14))
                expected = self.get_talib_ref(talib_func_name, self.df_pd, options)
                
                if expected is None: continue 

                if hasattr(module, "calculate_polars"):
                    expr = module.calculate_polars(indicator_name, options)
                    exprs = expr if isinstance(expr, list) else [expr]
                    res_pl = self.df_pl.select(exprs)
                    
                    warmup = 300 
                    
                    if isinstance(expected, tuple):
                        suffixes = ["__upper", "__mid", "__lower", "__macd", "__signal", "__hist", "__aroondown", "__aroonup"]
                        found_cols = [s for s in suffixes if f"{indicator_name}{s}" in res_pl.columns]
                        for i, s in enumerate(found_cols):
                            actual = res_pl[f"{indicator_name}{s}"].to_numpy()
                            np.testing.assert_allclose(actual[warmup:], expected[i][warmup:], atol=1e-8, equal_nan=True)
                    else:
                        if indicator_name in res_pl.columns:
                            actual = res_pl[indicator_name].to_numpy()
                        else:
                            actual = res_pl.to_numpy()[:, 0]
                        
                        np.testing.assert_allclose(actual[warmup:], expected[warmup:], atol=1e-8, equal_nan=True)

if __name__ == "__main__":
    unittest.main()