import pandas as pd
import numpy as np
from typing import List, Dict, Any

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: uo_7_14_28 -> {'p1': '7', 'p2': '14', 'p3': '28'}
    """
    return {
        "p1": args[0] if len(args) > 0 else "7",
        "p2": args[1] if len(args) > 1 else "14",
        "p3": args[2] if len(args) > 2 else "28"
    }

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    High-performance vectorized Ultimate Oscillator (UO).
    UO = 100 * [(4 * Avg7) + (2 * Avg14) + Avg28] / (4 + 2 + 1)
    """
    # 1. Parse Parameters
    try:
        p1 = int(options.get('p1', 7))
        p2 = int(options.get('p2', 14))
        p3 = int(options.get('p3', 28))
    except (ValueError, TypeError):
        p1, p2, p3 = 7, 14, 28

    # 2. Determine Price Precision
    try:
        sample_val = df['close'].iloc[0]
        sample_price = f"{sample_val:.10f}".rstrip('0')
        precision = len(sample_price.split('.')[1]) if '.' in sample_price else 2
        precision = min(max(precision, 2), 8) 
    except (IndexError, AttributeError, ValueError):
        precision = 2

    # 3. Vectorized Pre-calculations
    # Buying Pressure (BP) and True Range (TR) calculation
    prev_close = df['close'].shift(1)
    
    # bp = close - min(low, prev_close)
    min_low_pc = np.minimum(df['low'].values, prev_close.values)
    bp = df['close'] - min_low_pc
    
    # tr = max(high, prev_close) - min(low, prev_close)
    max_high_pc = np.maximum(df['high'].values, prev_close.values)
    tr = max_high_pc - min_low_pc
    
    # Handle division by zero for flat price action
    tr_series = pd.Series(tr, index=df.index).replace(0, np.nan)

    # 4. Vectorized Rolling Averages
    def get_avg(period):
        # Average = Sum(BP, n) / Sum(TR, n)
        return bp.rolling(window=period).sum() / tr_series.rolling(window=period).sum()

    avg1 = get_avg(p1)
    avg2 = get_avg(p2)
    avg3 = get_avg(p3)

    # 5. Ultimate Oscillator Formula
    uo = 100 * ((4 * avg1) + (2 * avg2) + avg3) / (4 + 2 + 1)

    # 6. Final Formatting and Rounding
    # Preserve original index for O(1) merging in parallel.py
    res = pd.DataFrame({
        'uo': uo.round(precision)
    }, index=df.index)
    
    # Drop rows where the longest window hasn't filled (warm-up period)
    return res.dropna(subset=['uo'])