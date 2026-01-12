import pandas as pd
import numpy as np
from typing import List, Dict, Any

def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for the Stochastic Oscillator.
    %K needs k_period, and %D needs d_period to average %K.
    We use 3x the primary period for engine-wide consistency.
    """
    try:
        k_period = int(options.get('k_period', 14))
    except (ValueError, TypeError):
        k_period = 14

    # 3x k_period ensures the rolling high/low extremes 
    # and the subsequent %D smoothing are well-established.
    return k_period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: stochastic_14_3 -> {'k_period': '14', 'd_period': '3'}
    """
    return {
        "k_period": args[0] if len(args) > 0 else "14",
        "d_period": args[1] if len(args) > 1 else "3"
    }

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    High-performance vectorized Stochastic Oscillator (%K and %D).
    %K = 100 * (Current Close - Lowest Low) / (Highest High - Lowest Low)
    %D = 3-period SMA of %K
    """
    # 1. Parse Parameters
    try:
        k_period = int(options.get('k_period', 14))
        d_period = int(options.get('d_period', 3))
    except (ValueError, TypeError):
        k_period, d_period = 14, 3

    # 2. Determine Precision
    # Oscillators are typically rounded to 2 decimals
    precision = 2 

    # 3. Vectorized Calculation Logic
    # Rolling Low and High over the k_period
    low_min = df['low'].rolling(window=k_period).min()
    high_max = df['high'].rolling(window=k_period).max()
    
    # Calculate %K
    # Handle division by zero for flat price action using .replace(0, np.nan)
    denom = (high_max - low_min).replace(0, np.nan)
    stoch_k = 100 * (df['close'] - low_min) / denom
    
    # Calculate %D (Simple Moving Average of %K)
    stoch_d = stoch_k.rolling(window=d_period).mean()

    # 4. Final Formatting and Rounding
    # Preserving the original index for O(1) merging in parallel.py
    res = pd.DataFrame({
        'stoch_k': stoch_k.round(precision),
        'stoch_d': stoch_d.round(precision)
    }, index=df.index)
    
    # Drop rows where the window hasn't filled (warm-up period)
    return res.dropna(subset=['stoch_d'])