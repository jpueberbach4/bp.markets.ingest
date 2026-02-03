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
    # format: volratio_PERIOD_STD_KCMULT
    # example: volratio_20_2.0_1.5
    return {
        "period": args[0] if len(args) > 0 else "20",
        "std_dev": args[1] if len(args) > 1 else "2.0",
        "kc_mult": args[2] if len(args) > 2 else "1.5"
    }

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    p = int(options.get('period', 20))
    std_dev_mult = float(options.get('std_dev', 2.0))
    kc_mult = float(options.get('kc_mult', 1.5))
    
    # 1. BBand Width
    # Width = (Mid + N*Std) - (Mid - N*Std) = 2 * N * Std
    std = pl.col("close").rolling_std(window_size=p)
    bb_width = std * (std_dev_mult * 2)
    
    # 2. Keltner Channel Width
    # Width = (EMA + M*ATR) - (EMA - M*ATR) = 2 * M * ATR
    # Note: Keltner usually uses EMA, but for width calculation, the central moving average cancels out.
    # We only need the volatility component (ATR).
    tr = pl.max_horizontal([
        (pl.col("high") - pl.col("low")),
        (pl.col("high") - pl.col("close").shift(1)).abs(),
        (pl.col("low") - pl.col("close").shift(1)).abs()
    ])
    atr = tr.rolling_mean(window_size=p)
    kc_width = atr * (kc_mult * 2)
    
    # 3. Ratio
    # Ratio < 1.0 means BB Width < KC Width (Squeeze is ON)
    ratio = bb_width / kc_width
    
    return [ratio.alias(f"{indicator_str}__ratio")]

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    p = int(options.get('period', 20))
    std_dev_mult = float(options.get('std_dev', 2.0))
    kc_mult = float(options.get('kc_mult', 1.5))
    
    # BB Width
    std = df['close'].rolling(p).std()
    bb_width = std * (std_dev_mult * 2)
    
    # KC Width
    tr = pd.concat([
        df['high'] - df['low'], 
        (df['high'] - df['close'].shift(1)).abs(), 
        (df['low'] - df['close'].shift(1)).abs()
    ], axis=1).max(axis=1)
    
    atr = tr.rolling(p).mean()
    kc_width = atr * (kc_mult * 2)
    
    return pd.DataFrame({'ratio': bb_width / kc_width}, index=df.index).dropna()