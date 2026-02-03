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
    # We need Period (ATR) + Period (Lookback)
    # Usually they are the same value 'p'
    return int(options.get('period', 10)) * 2

def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "period": args[0] if len(args) > 0 else "10", 
        "multiplier": args[1] if len(args) > 1 else "1.0",
        "lookback": args[2] if len(args) > 2 else None # Optional distinct lookback
    }

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    p = int(options.get('period', 10))
    m = float(options.get('multiplier', 1.0))
    # Default lookback to same as ATR period if not specified
    q = int(options.get('lookback', p))
    
    # 1. True Range Calculation
    # We use max_horizontal for efficiency in Polars
    tr = pl.max_horizontal([
        (pl.col("high") - pl.col("low")), 
        (pl.col("high") - pl.col("close").shift(1)).abs(),
        (pl.col("low") - pl.col("close").shift(1)).abs()
    ])
    atr = tr.rolling_mean(window_size=p)
    
    # 2. Calculate Raw Stops (The "First Step" in Chande's formula)
    # Long Stop Base = High_i - (ATR_i * Multiplier)
    # Short Stop Base = Low_i + (ATR_i * Multiplier)
    raw_long_stop = pl.col("high") - (atr * m)
    raw_short_stop = pl.col("low") + (atr * m)
    
    # 3. Apply the Lookback (The "Second Step")
    # Stop Long = Highest of Raw Long Stops over Q periods
    # Stop Short = Lowest of Raw Short Stops over Q periods
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
    
    # 1. ATR
    # Standard True Range
    tr = pd.concat([
        df['high'] - df['low'], 
        (df['high'] - df['close'].shift(1)).abs(), 
        (df['low'] - df['close'].shift(1)).abs()
    ], axis=1).max(axis=1)
    
    atr = tr.rolling(p).mean()
    
    # 2. Raw Stops
    raw_long = df['high'] - (atr * m)
    raw_short = df['low'] + (atr * m)
    
    # 3. Lookback Max/Min
    stop_long = raw_long.rolling(q).max()
    stop_short = raw_short.rolling(q).min()
    
    return pd.DataFrame({
        'stop_long': stop_long,
        'stop_short': stop_short
    }, index=df.index)