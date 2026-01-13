import pandas as pd
import numpy as np
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "The KDJ Indicator is a derived version of the Stochastic Oscillator "
        "used to identify trend strength and entry points. It consists of three "
        "lines: the K (fast), the D (slow), and the J (divergence). The J line "
        "represents the divergence of the K value from the D value, often acting "
        "as a lead indicator to signal overbought or oversold conditions before "
        "they appear in the standard K and D lines."
    )

def meta()->Dict:
    """
    Any other metadata to pass via API
    """
    return {
        "author": "Google Gemini",
        "version": 1.0
    }
    
def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for KDJ.
    KDJ requires 'n' rows for the initial RSV calculation, plus 
    stabilization for the K and D exponential moving averages.
    We use 3x 'n' for consistency and mathematical convergence.
    """
    try:
        n = int(options.get('n', 9))
    except (ValueError, TypeError):
        n = 9

    # Consistent with EMA and other oscillator stabilization buffers
    return n * 3

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