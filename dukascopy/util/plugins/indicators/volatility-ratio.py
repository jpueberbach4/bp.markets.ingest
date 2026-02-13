import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    return (
        "Volatility Ratio (TTM Squeeze) measures the relationship between Bollinger Bands "
        "and Keltner Channels. Ratio < 1.0 indicates a Squeeze (BB inside KC)."
    )

def meta() -> Dict:
    return {
        "author": "Google Gemini",
        "version": 1.1,
        "panel": 1,
        "verified": 1,
        "polars": 1
    }

def warmup_count(options: Dict[str, Any]) -> int:
    return int(options.get('period', 20)) * 2

def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "period": args[0] if len(args) > 0 else "20",
        "std_dev": args[1] if len(args) > 1 else "2.0",
        "kc_mult": args[2] if len(args) > 2 else "1.5"
    }

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    p = int(options.get('period', 20))
    std_dev_mult = float(options.get('std_dev', 2.0))
    kc_mult = float(options.get('kc_mult', 1.5))
    
    std = pl.col("close").rolling_std(window_size=p)
    bb_width = std * (std_dev_mult * 2)
    
    tr = pl.max_horizontal([
        (pl.col("high") - pl.col("low")),
        (pl.col("high") - pl.col("close").shift(1)).abs(),
        (pl.col("low") - pl.col("close").shift(1)).abs()
    ])
    atr = tr.rolling_mean(window_size=p)
    kc_width = atr * (kc_mult * 2)
    
    ratio = bb_width / kc_width
    
    return [ratio.alias(f"{indicator_str}__ratio")]

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    p = int(options.get('period', 20))
    std_dev_mult = float(options.get('std_dev', 2.0))
    kc_mult = float(options.get('kc_mult', 1.5))
    
    std = df['close'].rolling(p).std()
    bb_width = std * (std_dev_mult * 2)
    
    tr = pd.concat([
        df['high'] - df['low'], 
        (df['high'] - df['close'].shift(1)).abs(), 
        (df['low'] - df['close'].shift(1)).abs()
    ], axis=1).max(axis=1)
    
    atr = tr.rolling(p).mean()
    kc_width = atr * (kc_mult * 2)
    
    return pd.DataFrame({'ratio': bb_width / kc_width}, index=df.index).dropna()