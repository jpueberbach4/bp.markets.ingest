import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    return "Donchian Channel Width measures the range between the highest high and lowest low over N periods."

def meta() -> Dict:
    return {"author": "Google Gemini", "version": 1.0, "panel": 1, "verified": 1, "polars": 1}

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    p = int(options.get('period', 20))
    hh, ll = pl.col("high").rolling_max(window_size=p), pl.col("low").rolling_min(window_size=p)
    width = (hh - ll) / ((hh + ll) / 2)
    return [width.alias(f"{indicator_str}__width")]

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    p = int(options.get('period', 20))
    hh, ll = df['high'].rolling(p).max(), df['low'].rolling(p).min()
    return pd.DataFrame({'width': (hh - ll) / ((hh + ll) / 2)}, index=df.index).dropna()