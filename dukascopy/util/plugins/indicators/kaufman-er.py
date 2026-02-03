import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    return "Kaufman's Efficiency Ratio (ER) measures price 'congestion' or noise vs. trend strength."

def meta() -> Dict:
    return {"author": "Google Gemini", "version": 1.0, "panel": 1, "verified": 1, "polars": 1}

def warmup_count(options: Dict[str, Any]) -> int:
    return int(options.get('period', 10))

def position_args(args: List[str]) -> Dict[str, Any]:
    return {"period": args[0] if len(args) > 0 else "10"}

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    p = int(options.get('period', 10))
    direction = (pl.col("close") - pl.col("close").shift(p)).abs()
    volatility = (pl.col("close") - pl.col("close").shift(1)).abs().rolling_sum(window_size=p)
    er = direction / volatility
    return [er.alias(f"{indicator_str}__er")]

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    p = int(options.get('period', 10))
    direction = (df['close'] - df['close'].shift(p)).abs()
    volatility = (df['close'] - df['close'].shift(1)).abs().rolling(p).sum()
    return pd.DataFrame({'er': direction / volatility}, index=df.index)