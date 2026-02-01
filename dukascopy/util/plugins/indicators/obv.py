import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "On-Balance Volume (OBV) is a technical indicator that uses volume flow "
        "to predict changes in stock price. It relates price momentum to trading "
        "volume, acting as a cumulative total of volume: adding volume on up days "
        "and subtracting it on down days. It is primarily used to confirm trends "
        "or spot potential reversals through price-volume divergence."
    )

def meta() -> Dict:
    """
    Metadata for the dual-engine orchestrator.
    """
    return {
        "author": "Google Gemini",
        "version": 1.2,
        "panel": 1,
        "verified": 1,
        "polars": 0  # ENABLED: Native Polars support active
    }

def warmup_count(options: Dict[str, Any]) -> int:
    """
    OBV is a cumulative indicator. 
    A 100-bar buffer establishes a stable baseline for volume trends.
    """
    return 100

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    """
    return {}

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> pl.Expr:
    """
    Polars-native OBV designed for Float64 volume data.
    Explicitly aligns types to prevent Float64/Int64 reference panics.
    """
    
    # 1. Get the direction: 1.0, -1.0, or 0.0
    # .diff() results in null for the first row, so we fill with 0.0
    direction = (
        pl.col("close")
        .diff()
        .sign()
        .fill_null(0.0)
        .cast(pl.Float64)
    )

    # 2. Multiplication with volume (The Flow)
    # We cast volume to Float64 to match direction.
    # We fill_null(0.0) to ensure gaps in volume don't break the cumulative sum chain
    # (Polars cum_sum propagates nulls by default, unlike Pandas)
    obv_flow = (direction * pl.col("volume").cast(pl.Float64)).fill_null(0.0)

    # 3. Cumulative sum
    obv = obv_flow.cum_sum()

    return obv.round(2).alias(indicator_str)

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    Legacy fallback for Pandas-only environments.
    """
    # 1. Calculation Logic
    close_diff = df['close'].diff()
    
    # Vectorized direction mapping
    # np.where handles NaNs gracefully (comparisons with NaN are False)
    direction = np.where(close_diff > 0, 1, np.where(close_diff < 0, -1, 0))
    
    # Cumulative sum calculation
    # Pandas cumsum() automatically skips NaNs
    obv = (direction * df['volume']).cumsum()

    # 2. Final Formatting
    res = pd.DataFrame({
        'obv': obv.round(2)
    }, index=df.index)
    
    res['obv'] = res['obv'].fillna(0)
    
    return res