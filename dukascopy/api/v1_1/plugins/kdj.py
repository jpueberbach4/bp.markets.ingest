import pandas as pd
import numpy as np
from typing import List, Dict, Any

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: kdj_9_3_3 -> {'n': '9', 'm1': '3', 'm2': '3'}
    """
    return {
        "n": args[0] if len(args) > 0 else "9",
        "m1": args[1] if len(args) > 1 else "3",
        "m2": args[2] if len(args) > 2 else "3"
    }

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    High-performance vectorized KDJ calculation.
    K = EMA(RSV, m1), D = EMA(K, m2), J = 3K - 2D
    """
    # 1. Parse Parameters
    try:
        n = int(options.get('n', 9))      # Lookback period
        m1 = int(options.get('m1', 3))    # K slowing
        m2 = int(options.get('m2', 3))    # D slowing
    except (ValueError, TypeError):
        n, m1, m2 = 9, 3, 3

    # 2. Determine Precision
    precision = 2 # Standard for oscillators

    # 3. Calculate RSV (Raw Stochastic Value)
    low_min = df['low'].rolling(window=n).min()
    high_max = df['high'].rolling(window=n).max()
    
    # Handle division by zero for flat price action
    rsv = 100 * ((df['close'] - low_min) / (high_max - low_min).replace(0, np.nan))
    rsv = rsv.fillna(50) # Seed flat areas with neutral 50

    # 4. Vectorized K and D Calculation
    # The recursive KDJ formula is an EMA with alpha = 1/period
    # com = period - 1 is the equivalent Pandas 'com' parameter
    k = rsv.ewm(com=m1-1, adjust=False).mean()
    d = k.ewm(com=m2-1, adjust=False).mean()
    
    # 5. Calculate J Line
    j = (3 * k) - (2 * d)

    # 6. Final Formatting and Rounding
    # Preserving original index for O(1) merging in parallel.py
    res = pd.DataFrame({
        'k': k.round(precision),
        'd': d.round(precision),
        'j': j.round(precision)
    }, index=df.index)
    
    # Drop rows where the initial lookback hasn't filled
    return res.dropna(subset=['k'])