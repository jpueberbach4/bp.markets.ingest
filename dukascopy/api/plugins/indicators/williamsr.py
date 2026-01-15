import pandas as pd
import numpy as np
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "Williams %R (Williams Percent Range) is a momentum indicator that measures "
        "overbought and oversold levels, similar to a Stochastic Oscillator. It "
        "compares the current closing price to the high-low range over a specific "
        "period (typically 14). The scale ranges from 0 to -100; readings from 0 "
        "to -20 are considered overbought, while readings from -80 to -100 are "
        "considered oversold. It is particularly effective at identifying "
        "potential reversals and trend strength."
    )

def meta()->Dict:
    """
    Any other metadata to pass via API
    """
    return {
        "author": "Google Gemini",
        "version": 1.0,
        "panel": 1,
        "verified": 1
    }
    
def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for Williams %R.
    Requires a full 'period' to identify rolling highs and lows.
    We use 3x period for stability and engine-wide consistency.
    """
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14

    # 3x period ensures the rolling extremes are well-established
    return period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: williamsr_14 -> {'period': '14'}
    """
    return {
        "period": args[0] if len(args) > 0 else "14"
    }

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    High-performance vectorized Williams %R calculation.
    Formula: %R = (Highest High - Close) / (Highest High - Lowest Low) * -100
    """
    # 1. Parse Parameters
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14

    # 2. Determine Price Precision
    try:
        sample_val = df['close'].iloc[0]
        sample_price = f"{sample_val:.10f}".rstrip('0')
        precision = len(sample_price.split('.')[1]) if '.' in sample_price else 2
        precision = min(max(precision, 2), 8) 
    except (IndexError, AttributeError, ValueError):
        precision = 2

    # 3. Vectorized Calculation Logic
    # Get rolling high and low over the lookback period
    hh = df['high'].rolling(window=period).max()
    ll = df['low'].rolling(window=period).min()
    
    # Range calculation (Highest High - Lowest Low)
    # Handle division by zero for flat price action (HH == LL)
    range_diff = (hh - ll).replace(0, np.nan)
    
    # Williams %R Formula
    williams_r = ((hh - df['close']) / range_diff) * -100

    # 4. Final Formatting and Rounding
    # Preserving the original index for O(1) merging in parallel.py
    res = pd.DataFrame({
        'williams_r': williams_r.round(precision)
    }, index=df.index)
    
    # Drop rows where the window hasn't filled (warm-up period)
    return res.dropna(subset=['williams_r'])