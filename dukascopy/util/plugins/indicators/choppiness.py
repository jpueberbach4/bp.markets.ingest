import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    return "Choppiness Index values > 61.8 indicate a sideways market; < 38.2 indicate a strong trend."

def meta() -> Dict:
    return {"author": "Google Gemini", "version": 1.0, "panel": 1, "verified": 1, "polars": 1}

def warmup_count(options: Dict[str, Any]) -> int:
    return int(options.get('period', 14)) + 1

def position_args(args: List[str]) -> Dict[str, Any]:
    return {"period": args[0] if len(args) > 0 else "14"}

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    p = int(options.get('period', 14))
    
    # Scale: 100 * LOG10( SUM(ATR, n) / (MaxHigh - MinLow) ) / LOG10(n)
    tr = (pl.col("high") - pl.col("low")).rolling_sum(window_size=p)
    max_h = pl.col("high").rolling_max(window_size=p)
    min_l = pl.col("low").rolling_min(window_size=p)
    
    chop = 100 * ((tr / (max_h - min_l)).log(10) / (pl.lit(p).log(10)))
    
    return [chop.alias(f"{indicator_str}__value")]

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    p = int(options.get('period', 14))
    tr = (df['high'] - df['low']).rolling(p).sum()
    range_hl = df['high'].rolling(p).max() - df['low'].rolling(p).min()
    chop = 100 * (np.log10(tr / range_hl) / np.log10(p))
    return pd.DataFrame({'value': chop}, index=df.index)