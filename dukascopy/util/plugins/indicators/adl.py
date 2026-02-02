import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "Accumulation/Distribution Line (ADL) is a volume-based indicator that "
        "measures the cumulative flow of money into and out of an asset. It assesses "
        "buying and selling pressure by looking at where the price closes relative "
        "to its high-low range for the period."
    )

def meta()->Dict:
    """
    Metadata for the dual-engine orchestrator.
    """
    return {
        "author": "Google Gemini",
        "version": 1.1,
        "panel": 1,
        "verified": 1,
        "polars": 1  # Trigger high-speed Polars execution path
    }

def warmup_count(options: Dict[str, Any]) -> int:
    """
    ADL is a cumulative indicator. A warmup period ensures the 
    indicator has enough history to show a meaningful trend.
    """
    return 100

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    """
    return {}

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> pl.Expr:
    """
    High-performance Polars-native calculation for ADL.
    """
    # 1. Money Flow Multiplier (MFM)
    # Calculation: [(Close - Low) - (High - Close)] / (High - Low)
    h_l_range = pl.col("high") - pl.col("low")
    
    # Handle division by zero for flat bars where High == Low
    mfm = ((pl.col("close") - pl.col("low")) - (pl.col("high") - pl.col("close"))) / h_l_range
    
    # 2. Money Flow Volume (MFV)
    # Fill NaN/Null from division by zero with 0, then multiply by volume
    mfv = mfm.fill_nan(0).fill_null(0) * pl.col("volume")
    
    # 3. Cumulative Sum
    # Using the indicator_str as the alias for orchestrator compatibility
    return mfv.cum_sum().alias(indicator_str)

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    Legacy Pandas fallback.
    """
    h_l_range = (df['high'] - df['low']).replace(0, np.nan)
    mfm = ((df['close'] - df['low']) - (df['high'] - df['close'])) / h_l_range
    mfm = mfm.fillna(0)
    
    mfv = mfm * df['volume']
    adl = mfv.cumsum()

    return pd.DataFrame({'adl': adl}, index=df.index)