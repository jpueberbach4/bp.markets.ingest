import pandas as pd
import numpy as np
from typing import List, Dict, Any

def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for the Money Flow Index.
    MFI requires a full 'period' to calculate the initial Money Flow Ratio.
    We use 3x period for stability and consistency across the engine.
    """
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14

    # Consistent with other rolling-window stabilization buffers
    return period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: mfi_14 -> {'period': '14'}
    """
    return {
        "period": args[0] if len(args) > 0 else "14"
    }

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    High-performance vectorized Money Flow Index (MFI) calculation.
    MFI = 100 - (100 / (1 + (Positive Money Flow / Negative Money Flow)))
    """
    # 1. Parse Parameters
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14

    # 2. Determine Precision
    precision = 2 # Oscillators are typically rounded to 2 decimals

    # 3. Calculation Logic
    # Typical Price
    tp = (df['high'] + df['low'] + df['close']) / 3
    
    # Raw Money Flow
    rmf = tp * df['volume']
    
    # Determine Positive and Negative Money Flow (Vectorized)
    tp_shift = tp.shift(1)
    pos_mf = rmf.where(tp > tp_shift, 0)
    neg_mf = rmf.where(tp < tp_shift, 0)
    
    # Rolling Sums for the Money Flow Ratio
    mfr_pos = pos_mf.rolling(window=period).sum()
    mfr_neg = neg_mf.rolling(window=period).sum()
    
    # Handle division by zero for flat periods
    mf_ratio = mfr_pos / mfr_neg.replace(0, np.nan)
    
    # MFI Formula
    mfi = 100 - (100 / (1 + mf_ratio))
    # If no negative flow exists, MFI is 100; if no positive flow, it's 0
    mfi = mfi.fillna(method='ffill').fillna(50) 

    # 4. Final Formatting and Rounding
    # Preserving the original index for O(1) merging in parallel.py
    res = pd.DataFrame({
        'mfi': mfi.round(precision)
    }, index=df.index)
    
    # Drop rows where the window hasn't filled (warm-up period)
    return res.dropna(subset=['mfi'])