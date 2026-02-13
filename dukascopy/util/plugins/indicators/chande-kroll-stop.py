import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    return "Chande Kroll Stop: A trend-following stop-loss indicator calculated using the highest/lowest of volatility-adjusted prices."

def meta() -> Dict:
    return {
        "author": "Google Gemini", 
        "version": 2.0, 
        "panel": 0, 
        "verified": 1, 
        "polars": 1
    }

def warmup_count(options: Dict[str, Any]) -> int:
    p = int(options.get('period', 10))
    q = int(options.get('lookback', p))
    return p + q

def position_args(args: List[str]) -> Dict[str, Any]:
    p = args[0] if len(args) > 0 else "10"
    return {
        "period": p, 
        "multiplier": args[1] if len(args) > 1 else "1.0",
        "lookback": args[2] if len(args) > 2 else p # Default to same as period
    }

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    p = int(options.get('period', 10))
    m = float(options.get('multiplier', 1.0))
    q = int(options.get('lookback', p))
    
    tr = pl.max_horizontal([
        (pl.col("high") - pl.col("low")), 
        (pl.col("high") - pl.col("close").shift(1)).abs(),
        (pl.col("low") - pl.col("close").shift(1)).abs()
    ])
    atr = tr.rolling_mean(window_size=p)

    raw_long_stop = pl.col("high") - (atr * m)
    raw_short_stop = pl.col("low") + (atr * m)

    stop_long = raw_long_stop.rolling_max(window_size=q)
    stop_short = raw_short_stop.rolling_min(window_size=q)
    
    return [
        stop_long.alias(f"{indicator_str}__stop_long"),
        stop_short.alias(f"{indicator_str}__stop_short")
    ]

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    p = int(options.get('period', 10))
    m = float(options.get('multiplier', 1.0))
    q = int(options.get('lookback', p))
    
    tr = pd.concat([
        df['high'] - df['low'], 
        (df['high'] - df['close'].shift(1)).abs(), 
        (df['low'] - df['close'].shift(1)).abs()
    ], axis=1).max(axis=1)
    
    atr = tr.rolling(p).mean()
    
    raw_long = df['high'] - (atr * m)
    raw_short = df['low'] + (atr * m)
    
    stop_long = raw_long.rolling(q).max()
    stop_short = raw_short.rolling(q).min()
    
    return pd.DataFrame({
        'stop_long': stop_long,
        'stop_short': stop_short
    }, index=df.index)