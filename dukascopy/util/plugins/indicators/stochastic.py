import polars as pl
import pandas as pd
import numpy as np
from typing import List, Dict, Any

def description() -> str:
    return (
        "The Stochastic Oscillator (Slow) compares a closing price to its price range "
        "over a period. It consists of %K (Slow) and %D (Slow). Readings above 80 are "
        "overbought, below 20 are oversold."
    )

def meta() -> Dict:
    return {
        "author": "Google Gemini",
        "version": 1.3,
        "panel": 1,
        "verified": 1,
        "talib-validated": 1, 
        "polars": 1
    }

def warmup_count(options: Dict[str, Any]) -> int:
    try:
        k_p = int(options.get('k_period', 5))
        sk_p = int(options.get('sk_period', 3))
        sd_p = int(options.get('sd_period', 3))
    except (ValueError, TypeError):
        k_p, sk_p, sd_p = 5, 3, 3
    return k_p + sk_p + sd_p

def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "k_period": args[0] if len(args) > 0 else "5",
        "sk_period": args[1] if len(args) > 1 else "3",
        "sd_period": args[2] if len(args) > 2 else "3"
    }

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    """
    High-performance Polars-native Slow Stochastic.
    Matches TA-Lib 'STOCH' logic: 
    1. RawK = 100 * (Close - LowMin) / (HighMax - LowMin)
    2. SlowK = SMA(RawK, sk_period)
    3. SlowD = SMA(SlowK, sd_period)
    """
    try:
        k_p = int(options.get('k_period', 5))
        sk_p = int(options.get('sk_period', 3))
        sd_p = int(options.get('sd_period', 3))
    except (ValueError, TypeError):
        k_p, sk_p, sd_p = 5, 3, 3

    low_min = pl.col("low").rolling_min(window_size=k_p)
    high_max = pl.col("high").rolling_max(window_size=k_p)
    
    denom = high_max - low_min
    raw_k = (100 * (pl.col("close") - low_min) / denom)
    slow_k = raw_k.rolling_mean(window_size=sk_p)
    
    slow_d = slow_k.rolling_mean(window_size=sd_p)

    return [
        slow_k.alias(f"{indicator_str}__stoch_k"),
        slow_d.alias(f"{indicator_str}__stoch_d")
    ]

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    try:
        import talib
        k_p = int(options.get('k_period', 5))
        sk_p = int(options.get('sk_period', 3))
        sd_p = int(options.get('sd_period', 3))
        
        slowk, slowd = talib.STOCH(
            df['high'].values, df['low'].values, df['close'].values,
            fastk_period=k_p, slowk_period=sk_p, slowk_matype=0,
            slowd_period=sd_p, slowd_matype=0
        )
    except ImportError:
        slowk, slowd = np.nan, np.nan
        
    return pd.DataFrame({
        'stoch_k': slowk,
        'stoch_d': slowd
    }, index=df.index).dropna()