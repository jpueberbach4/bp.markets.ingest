import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    return "Volume Weighted Moving Average (VWMA) weights price by volume, emphasizing price action on high volume bars."

def meta() -> Dict:
    return {"author": "Google Gemini", "version": 1.0, "panel": 0, "verified": 1, "polars": 1}

def warmup_count(options: Dict[str, Any]) -> int:
    return int(options.get('period', 20))

def position_args(args: List[str]) -> Dict[str, Any]:
    return {"period": args[0] if len(args) > 0 else "20"}

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    p = int(options.get('period', 20))
    pv = pl.col("close") * pl.col("volume")
    vwma = pv.rolling_sum(window_size=p) / pl.col("volume").rolling_sum(window_size=p)
    return [vwma.alias(f"{indicator_str}__value")]

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    p = int(options.get('period', 20))
    vwma = (df['close'] * df['volume']).rolling(p).sum() / df['volume'].rolling(p).sum()
    return pd.DataFrame({'value': vwma}, index=df.index)