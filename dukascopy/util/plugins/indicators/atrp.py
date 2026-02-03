import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    return "ATR Percent (ATRP) normalizes volatility as a percentage of price for cross-asset comparison."

def meta() -> Dict:
    return {"author": "Google Gemini", "version": 1.0, "panel": 1, "verified": 1, "polars": 1}

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    p = int(options.get('period', 14))
    tr = pl.max_horizontal([(pl.col("high") - pl.col("low")), (pl.col("high") - pl.col("close").shift(1)).abs()])
    atrp = (tr.rolling_mean(window_size=p) / pl.col("close")) * 100
    return [atrp.alias(f"{indicator_str}__atrp")]

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    p = int(options.get('period', 14))
    tr = pd.concat([df['high'] - df['low'], (df['high'] - df['close'].shift(1)).abs()], axis=1).max(axis=1)
    atrp = (tr.rolling(p).mean() / df['close']) * 100
    return pd.DataFrame({'atrp': atrp}, index=df.index).dropna()