import pandas as pd
import numpy as np
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "The Aroon Indicator identifies whether an asset is trending and the "
        "strength of that trend. It consists of 'Aroon Up' (measuring the time "
        "since the highest high) and 'Aroon Down' (measuring the time since the "
        "lowest low). Values near 100 indicate a strong trend, while values "
        "near 0 suggest a weak trend or consolidation."
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
    Calculates the required warmup rows for the Aroon Indicator.
    Aroon is based on a rolling window of (period + 1) to determine
    the number of days since a high or low.
    """
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14

    # We need the full window plus a small buffer to ensure 
    # the first row after the warmup has stable values.
    # window = period + 1
    return period + 2

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: aroon_14 -> {'period': '14'}
    """
    return {
        "period": args[0] if len(args) > 0 else "14"
    }

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    High-performance vectorized Aroon Indicator calculation.
    """
    # 1. Parse Period
    try:
        period = int(options.get('period', 25))
    except (ValueError, TypeError):
        period = 25

    # 2. Determine Price Precision for rounding
    try:
        sample_price = str(df['close'].iloc[0])
        precision = len(sample_price.split('.')[1]) if '.' in sample_price else 2
    except (IndexError, AttributeError):
        precision = 2

    # 3. Calculation Logic
    # Aroon Up/Down = ((period - days since n-period extreme) / period) * 100
    # We use a window of period + 1 to account for the current bar
    window = period + 1
    
    # Vectorized argmax/argmin over a rolling window
    # These return the relative index (0 to period) of the high/low
    aroon_up_days = df['high'].rolling(window=window).apply(lambda x: x.argmax(), raw=True)
    aroon_down_days = df['low'].rolling(window=window).apply(lambda x: x.argmin(), raw=True)

    # Convert relative index to "days since" and calculate percentage
    # In a window of size 26, the current bar is index 25 (argmax=25 means 0 days ago)
    res_up = (aroon_up_days / period) * 100
    res_down = (aroon_down_days / period) * 100

    # 4. Final Formatting and Rounding
    res = pd.DataFrame({
        'aroon_up': res_up.round(precision),
        'aroon_down': res_down.round(precision)
    }, index=df.index)
    
    # Drop rows where the window hasn't filled yet (warmup period)
    return res.dropna()