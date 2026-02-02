import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "The Money Flow Index (MFI) is a technical oscillator that uses both price "
        "and volume data to identify overbought or oversold conditions in an asset. "
        "Often described as a volume-weighted RSI, it measures the 'enthusiasm' of "
        "a trend by looking at the typical price and money flow over a set period. "
        "Values above 80 are generally considered overbought, while values below 20 "
        "are considered oversold."
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
    Calculates the required warmup rows for the Money Flow Index.
    """
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14
    return period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    """
    return {
        "period": args[0] if len(args) > 0 else "14"
    }

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> pl.Expr:
    """
    High-performance Polars-native calculation for MFI.
    """
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14

    # 1. Typical Price and Raw Money Flow
    tp = (pl.col("high") + pl.col("low") + pl.col("close")) / 3
    rmf = tp * pl.col("volume")

    # 2. Determine Positive and Negative Money Flow
    # Compare current Typical Price to previous Typical Price
    tp_diff = tp.diff()
    
    pos_mf = pl.when(tp_diff > 0).then(rmf).otherwise(0)
    neg_mf = pl.when(tp_diff < 0).then(rmf).otherwise(0)

    # 3. Rolling Sums and Money Flow Ratio
    mfr_pos = pos_mf.rolling_sum(window_size=period)
    mfr_neg = neg_mf.rolling_sum(window_size=period)

    # 4. MFI Formula: 100 - (100 / (1 + (pos/neg)))
    # Handling division by zero via null conversion
    mf_ratio = mfr_pos / mfr_neg
    mfi = 100 - (100 / (1 + mf_ratio))

    # 5. Final Formatting
    # Replicating the fillna(50) logic for stable outputs on flat data
    return mfi.fill_nan(50).fill_null(50).round(2).alias(indicator_str)

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    Legacy fallback for Pandas-only environments.
    """
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14

    precision = 2 

    tp = (df['high'] + df['low'] + df['close']) / 3
    rmf = tp * df['volume']
    
    tp_shift = tp.shift(1)
    pos_mf = rmf.where(tp > tp_shift, 0)
    neg_mf = rmf.where(tp < tp_shift, 0)
    
    mfr_pos = pos_mf.rolling(window=period).sum()
    mfr_neg = neg_mf.rolling(window=period).sum()
    
    mf_ratio = mfr_pos / mfr_neg.replace(0, np.nan)
    
    mfi = 100 - (100 / (1 + mf_ratio))
    mfi = mfi.ffill().fillna(50) 

    res = pd.DataFrame({
        'mfi': mfi.round(precision)
    }, index=df.index)
    
    return res.dropna(subset=['mfi'])