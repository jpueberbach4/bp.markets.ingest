import pandas as pd
import numpy as np
from typing import List, Dict, Any

def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for Keltner Channels.
    Keltner Channels use an EMA for the Mid Line and Wilder's Smoothing 
    for the ATR. We use 3x the largest period to ensure both converge.
    """
    try:
        ema_period = int(options.get('period', 20))
        atr_period = int(options.get('atr_period', 10))
    except (ValueError, TypeError):
        ema_period, atr_period = 20, 10

    # Determine the limiting factor
    max_period = max(ema_period, atr_period)

    # 3x multiplier ensures EMA and Wilder's smoothing are accurate
    return max_period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: keltner_20_10_2 -> {'period': '20', 'atr_period': '10', 'multiplier': '2'}
    """
    return {
        "period": args[0] if len(args) > 0 else "20",
        "atr_period": args[1] if len(args) > 1 else "10",
        "multiplier": args[2] if len(args) > 2 else "2.0"
    }

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    High-performance vectorized Keltner Channels calculation.
    - Mid Line: EMA(period)
    - ATR: Wilder's smoothed True Range
    - Bands: Mid +/- (Multiplier * ATR)
    """
    # 1. Parse Parameters
    try:
        ema_period = int(options.get('period', 20))
        atr_period = int(options.get('atr_period', 10))
        multiplier = float(options.get('multiplier', 2.0))
    except (ValueError, TypeError):
        ema_period, atr_period, multiplier = 20, 10, 2.0

    # 2. Determine Price Precision
    try:
        sample_price = str(df['close'].iloc[0])
        precision = len(sample_price.split('.')[1]) if '.' in sample_price else 2
    except (IndexError, AttributeError):
        precision = 5

    # 3. Calculation Logic
    # A. Mid Line (EMA)
    mid = df['close'].ewm(span=ema_period, adjust=False).mean()

    # B. True Range (Vectorized)
    prev_close = df['close'].shift(1)
    tr1 = df['high'] - df['low']
    tr2 = (df['high'] - prev_close).abs()
    tr3 = (df['low'] - prev_close).abs()
    
    # Combined True Range is the maximum of the three measures
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # C. ATR (Wilder's Smoothing)
    # Wilder's Smoothing alpha = 1 / period
    atr = true_range.ewm(alpha=1/atr_period, min_periods=atr_period).mean()

    # D. Calculate Bands
    upper = mid + (multiplier * atr)
    lower = mid - (multiplier * atr)

    # 4. Final Formatting and Rounding
    # Preserving the original index for O(1) merging in parallel.py
    res = pd.DataFrame({
        'upper': upper.round(precision),
        'mid': mid.round(precision),
        'lower': lower.round(precision)
    }, index=df.index)
    
    # Drop rows where both EMA and ATR haven't stabilized
    warmup = max(ema_period, atr_period)
    return res.dropna(subset=['upper']).iloc[warmup:]