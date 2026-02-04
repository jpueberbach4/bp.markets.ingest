import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    return "On-Balance Volume (OBV) matches TA-Lib by seeding the first bar with volume."

def meta() -> Dict:
    return {"author": "Google Gemini", "version": 1.6, "panel": 1, "verified": 1, "talib-validated": 1,  "polars": 1}

def position_args(args: List[str]) -> Dict[str, Any]:
    return {}

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> pl.Expr:
    diff = pl.col("close").diff()
    flow = (
        pl.when(diff.is_null()) # This is Row 0
        .then(pl.col("volume"))
        .when(diff > 0).then(pl.col("volume"))
        .when(diff < 0).then(-pl.col("volume"))
        .otherwise(0.0)
    )

    return flow.cum_sum().alias(indicator_str)

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """Pandas fallback aligned with TA-Lib baseline."""
    close_diff = df['close'].diff()
    
    flow = np.zeros(len(df))
    
    flow[0] = df['volume'].iloc[0]
    
    mask_up = close_diff[1:] > 0
    mask_down = close_diff[1:] < 0
    
    flow[1:][mask_up] = df['volume'].iloc[1:][mask_up]
    flow[1:][mask_down] = -df['volume'].iloc[1:][mask_down]
    
    return pd.DataFrame({'obv': np.cumsum(flow)}, index=df.index)