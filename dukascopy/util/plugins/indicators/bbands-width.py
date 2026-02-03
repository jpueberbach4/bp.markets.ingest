import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    return "Bollinger Band Width (volatility intensity) and %B (price position relative to bands)."

def meta() -> Dict:
    return {"author": "Google Gemini", "version": 1.0, "panel": 1, "verified": 1, "polars": 1}

def position_args(args: List[str]) -> Dict[str, Any]:
    return {"period": args[0] if len(args) > 0 else "20", "std": args[1] if len(args) > 1 else "2.0"}

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    p, s = int(options.get('period', 20)), float(options.get('std', 2.0))
    mid = pl.col("close").rolling_mean(window_size=p)
    std = pl.col("close").rolling_std(window_size=p)
    
    upper, lower = mid + (std * s), mid - (std * s)
    width = (upper - lower) / mid
    pct_b = (pl.col("close") - lower) / (upper - lower)
    
    return [width.alias(f"{indicator_str}__width"), pct_b.alias(f"{indicator_str}__pct_b")]

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    p, s = int(options.get('period', 20)), float(options.get('std', 2.0))
    mid = df['close'].rolling(p).mean()
    std = df['close'].rolling(p).std()
    upper, lower = mid + (std * s), mid - (std * s)
    return pd.DataFrame({'width': (upper - lower) / mid, 'pct_b': (df['close'] - lower) / (upper - lower)}, index=df.index).dropna()