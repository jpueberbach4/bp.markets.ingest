import pandas as pd
import numpy as np
from typing import List, Dict, Any


def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "Donchian Channels are a volatility indicator used to identify trend "
        "extremes and potential breakouts. It plots three lines: the Upper Band "
        "(highest price over the period), the Lower Band (lowest price over the "
        "period), and the Midline (average of the Upper and Lower bands)."
    )

def meta()->Dict:
    """
    Any other metadata to pass via API
    """
    return {
        "author": "Google Gemini",
        "version": 1.0,
        "verified": 1,
        "needs": "surface-colour"
    }
    
def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for Donchian Channels.
    Donchian Channels require a full 'period' to find the highest high 
    and lowest low. We use 3x period for stability and consistency.
    """
    try:
        period = int(options.get('period', 20))
    except (ValueError, TypeError):
        period = 20

    # Consistent with SMA and Bollinger Bands stabilization buffers
    return period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: donchian_20 -> {'period': '20'}
    """
    return {
        "period": args[0] if len(args) > 0 else "20"
    }

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    High-performance vectorized Donchian Channels calculation.
    Formula:
    - Upper: Highest High over N periods
    - Lower: Lowest Low over N periods
    - Mid:   (Upper + Lower) / 2
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

    # 3. Vectorized Calculation
    # We use a rolling window to find the extremes
    upper = df['high'].rolling(window=period).max()
    lower = df['low'].rolling(window=period).min()
    mid = (upper + lower) / 2

    # 4. Final Formatting and Rounding
    # We return a DataFrame with the same index as the input for O(1) merging
    res = pd.DataFrame({
        'upper': upper.round(precision),
        'mid': mid.round(precision),
        'lower': lower.round(precision)
    }, index=df.index)
    
    # Drop rows where the rolling window hasn't filled (warmup period)
    return res.dropna(subset=['upper'])