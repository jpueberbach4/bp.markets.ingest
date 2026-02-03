import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    return "Volatility Quality Index (VQI) distinguishes between trending volatility and noisy churn."

def meta() -> Dict:
    return {"author": "Google Gemini", "version": 1.0, "panel": 1, "verified": 1, "polars": 1}

def warmup_count(options: Dict[str, Any]) -> int:
    return int(options.get('period', 10)) + 1

def position_args(args: List[str]) -> Dict[str, Any]:
    return {"period": args[0] if len(args) > 0 else "10"}

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    p = int(options.get('period', 10))
    # VQI calculation logic
    tr = (pl.col("high") - pl.col("low")).abs()
    vqi = ((pl.col("close") - pl.col("close").shift(1)) / tr).abs().rolling_mean(window_size=p)
    return [vqi.alias(f"{indicator_str}__value")]

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    p = int(options.get('period', 10))
    tr = (df['high'] - df['low']).abs()
    vqi = ((df['close'] - df['close'].shift(1)) / tr).abs().rolling(p).mean()
    return pd.DataFrame({'value': vqi}, index=df.index)