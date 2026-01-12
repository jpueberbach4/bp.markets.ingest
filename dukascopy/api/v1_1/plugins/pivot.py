import pandas as pd
import numpy as np
from typing import List, Dict, Any

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: pivot_1 -> {'lookback': '1'}
    """
    return {
        "lookback": args[0] if len(args) > 0 else "1"
    }

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    High-performance vectorized Standard Pivot Points (Floor Pivots).
    Calculates levels based on the High, Low, and Close of the previous period.
    """
    # 1. Parse Parameters
    try:
        period = int(options.get('lookback', 1))
    except (ValueError, TypeError):
        period = 1

    # 2. Determine Price Precision
    try:
        sample_price = str(df['close'].iloc[0])
        precision = len(sample_price.split('.')[1]) if '.' in sample_price else 2
    except (IndexError, AttributeError):
        precision = 5

    # 3. Vectorized Calculation Logic
    # We look at the extremes of the PREVIOUS period(s)
    prev_h = df['high'].shift(1).rolling(window=period).max()
    prev_l = df['low'].shift(1).rolling(window=period).min()
    prev_c = df['close'].shift(1)

    # Pivot Point (PP)
    pp = (prev_h + prev_l + prev_c) / 3
    
    # Resistance Levels
    r1 = (2 * pp) - prev_l
    r2 = pp + (prev_h - prev_l)
    
    # Support Levels
    s1 = (2 * pp) - prev_h
    s2 = pp - (prev_h - prev_l)

    # 4. Final Formatting and Rounding
    # Preserving the original index for O(1) merging in parallel.py
    res = pd.DataFrame({
        'pp': pp.round(precision),
        'r1': r1.round(precision),
        's1': s1.round(precision),
        'r2': r2.round(precision),
        's2': s2.round(precision)
    }, index=df.index)
    
    # Drop rows where the lookback hasn't filled (warm-up period)
    return res.dropna(subset=['pp'])