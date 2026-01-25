import pandas as pd
import numpy as np
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "Fibonacci Retracements identify potential support and resistance levels "
        "based on the golden ratio. It calculates the vertical distance between "
        "the highest high and lowest low over a set period and plots horizontal "
        "lines at the key Fibonacci levels (23.6%, 38.2%, 50%, 61.8%, and 78.6%). "
        "Traders use these levels to identify areas where a price correction might "
        "reverse and join the primary trend."
    )

def meta()->Dict:
    """
    Any other metadata to pass via API
    """
    return {
        "author": "Google Gemini",
        "version": 1.0,
        "verified": 1,
        "needs": "extension"
    }
    
def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for Fibonacci Retracements.
    Requires a full 'period' to identify the rolling High/Low extremes.
    We use 3x period for stability and consistency across the engine.
    """
    try:
        period = int(options.get('period', 100))
    except (ValueError, TypeError):
        period = 100

    # Consistent with SMA and Donchian stabilization buffers
    return period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: fibonacci_100 -> {'period': '100'}
    """
    return {
        "period": args[0] if len(args) > 0 else "100"
    }

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    High-performance vectorized Fibonacci Retracement calculation.
    Calculates levels (0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0) based on 
    rolling High/Low extremes over a specific period.
    """
    # 1. Parse Parameters
    try:
        period = int(options.get('period', 100))
    except (ValueError, TypeError):
        period = 100

    # 2. Determine Price Precision for rounding
    try:
        sample_price = str(df['close'].iloc[0])
        precision = len(sample_price.split('.')[1])+1 if '.' in sample_price else 2
    except (IndexError, AttributeError):
        precision = 5

    # 3. Calculate Rolling Extremes (HH and LL)
    hh = df['high'].rolling(window=period).max()
    ll = df['low'].rolling(window=period).min()
    diff = hh - ll

    # 4. Vectorized Level Calculation
    # We create a dictionary of levels to easily convert to a DataFrame
    levels = {
        'fib_0': hh,
        'fib_236': hh - (0.236 * diff),
        'fib_382': hh - (0.382 * diff),
        'fib_50': hh - (0.5 * diff),
        'fib_618': hh - (0.618 * diff),
        'fib_786': hh - (0.786 * diff),
        'fib_100': ll
    }

    # 5. Final Formatting and Rounding
    res = pd.DataFrame(levels, index=df.index)
    
    # Round all columns to detected price precision
    res = res.round(precision)
    
    # Drop rows where the window hasn't filled (warm-up period)
    return res.dropna()