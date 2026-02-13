import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    return "Ease of Movement (EOM) relates price change to volume to show the efficiency of price movement."

def meta() -> Dict:
    return {"author": "Google Gemini", "version": 1.0, "panel": 1, "verified": 1, "talib-validated": 1, "polars": 1}

def warmup_count(options: Dict[str, Any]) -> int:
    return int(options.get('period', 14)) + 1

def position_args(args: List[str]) -> Dict[str, Any]:
    return {"period": args[0] if len(args) > 0 else "14"}

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    p = int(options.get('period', 14))
    mid = (pl.col("high") + pl.col("low")) / 2
    distance = mid - mid.shift(1)
    box_ratio = (pl.col("volume") / 1000000) / (pl.col("high") - pl.col("low"))
    eom = distance / box_ratio
    return [eom.rolling_mean(window_size=p).alias(f"{indicator_str}__value")]

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    p = int(options.get('period', 14))
    mid = (df['high'] + df['low']) / 2
    dist = mid - mid.shift(1)
    box = (df['volume'] / 1000000) / (df['high'] - df['low'])
    return pd.DataFrame({'value': (dist / box).rolling(p).mean()}, index=df.index).dropna()