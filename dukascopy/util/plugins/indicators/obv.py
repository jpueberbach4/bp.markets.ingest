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
        "version": 1.1,
        "panel": 1,
        "verified": 1,
        "polars": 1  # Flag to trigger high-speed Polars execution
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
    High-performance Polars-native calculation for OBV.
    """
    # 1. Determine direction: 1 for up, -1 for down, 0 for flat
    # We use .diff() and sign() to handle direction in one vectorized pass
    direction = (pl.col("close").diff()).sign().fill_null(0)

    # 2. Cumulative sum of (direction * volume)
    # OBV is inherently path-dependent; cum_sum is the optimized Rust path.
    obv = (direction * pl.col("volume")).cum_sum()

    # 3. Final Formatting
    return obv.round(2).alias(indicator_str)

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    Legacy fallback for Pandas-only environments.
    """
    # 1. Calculation Logic
    close_diff = df['close'].diff()
    
    # Vectorized direction mapping
    direction = np.where(close_diff > 0, 1, np.where(close_diff < 0, -1, 0))
    
    # Cumulative sum calculation
    obv = (direction * df['volume']).cumsum()

    # 2. Final Formatting
    res = pd.DataFrame({
        'obv': obv.round(2)
    }, index=df.index)
    
    res['obv'] = res['obv'].fillna(0)
    
    return res