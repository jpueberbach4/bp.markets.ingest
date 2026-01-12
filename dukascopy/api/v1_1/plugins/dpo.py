import pandas as pd
import numpy as np
from typing import List, Dict, Any

def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for DPO.
    DPO requires a full SMA period PLUS a shift of (period/2 + 1).
    We use a 3x multiplier on the total logic to ensure stability.
    """
    try:
        period = int(options.get('period', 20))
    except (ValueError, TypeError):
        period = 20

    # Mathematical requirements:
    # 1. The SMA needs 'period' rows.
    # 2. The shift needs 'period/2 + 1' rows.
    base_requirement = period + int((period / 2) + 1)
    
    # We apply a buffer to stay consistent with other indicators
    return base_requirement + period

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: dpo_20 -> {'period': '20'}
    """
    return {
        "period": args[0] if len(args) > 0 else "20"
    }

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    High-performance vectorized Detrended Price Oscillator (DPO) calculation.
    Formula: Price((period/2) + 1 periods ago) - SMA(period)
    """
    # 1. Parse Parameters
    try:
        period = int(options.get('period', 20))
    except (ValueError, TypeError):
        period = 20

    # 2. Determine Price Precision for rounding
    try:
        sample_price = str(df['close'].iloc[0])
        precision = len(sample_price.split('.')[1]) if '.' in sample_price else 2
    except (IndexError, AttributeError):
        precision = 5

    # 3. Calculation Logic
    # Calculate Simple Moving Average (SMA)
    sma = df['close'].rolling(window=period).mean()
    
    # Calculate the shift back: (period / 2) + 1
    # This aligns the current SMA with a past price point to remove the trend
    lookback_shift = int((period / 2) + 1)
    
    # DPO calculation: Shifting the price back to compare against the SMA
    dpo = df['close'].shift(lookback_shift) - sma

    # 4. Final Formatting and Rounding
    # Preserving the original index for O(1) merging in parallel.py
    res = pd.DataFrame({
        'dpo': dpo.round(precision)
    }, index=df.index)
    
    # Drop rows where DPO is NaN (warm-up period and the lookback shift lag)
    return res.dropna(subset=['dpo'])