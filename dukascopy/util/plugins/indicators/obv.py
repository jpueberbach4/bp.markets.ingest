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
    # 1. We need the price difference to determine direction
    diff = pl.col("close").diff()

    # 2. SEED LOGIC: 
    # TA-Lib OBV starts at the first bar's volume.
    # We use pl.arg_unique() or a simple row_index check if available, 
    # but the most robust way in a plugin is checking for the null diff.
    
    flow = (
        pl.when(diff.is_null()) # This is Row 0
        .then(pl.col("volume"))
        .when(diff > 0).then(pl.col("volume"))
        .when(diff < 0).then(-pl.col("volume"))
        .otherwise(0.0)
    )

    # 3. Cumulative Sum
    return flow.cum_sum().alias(indicator_str)

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """Pandas fallback aligned with TA-Lib baseline."""
    # Ensure we use the exact same logic as the Polars engine
    close_diff = df['close'].diff()
    
    # Initialize flow array
    flow = np.zeros(len(df))
    
    # Handle the first row seed (TA-Lib standard)
    flow[0] = df['volume'].iloc[0]
    
    # Handle subsequent rows
    # Index 1 onwards
    mask_up = close_diff[1:] > 0
    mask_down = close_diff[1:] < 0
    
    flow[1:][mask_up] = df['volume'].iloc[1:][mask_up]
    flow[1:][mask_down] = -df['volume'].iloc[1:][mask_down]
    
    return pd.DataFrame({'obv': np.cumsum(flow)}, index=df.index)