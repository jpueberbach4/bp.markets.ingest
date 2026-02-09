import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "The Aroon Indicator identifies whether an asset is trending and the "
        "strength of that trend. It consists of 'Aroon Up' (measuring the time "
        "since the highest high) and 'Aroon Down' (measuring the time since the "
        "lowest low)."
    )

def meta() -> Dict:
    """
    Metadata for the dual-engine orchestrator.
    """
    return {
        "author": "Google Gemini",
        "version": 1.1,
        "panel": 1,
        "verified": 1,
        "talib-validated": 1, 
        "polars": 0  # Trigger high-speed Polars execution path
    }

def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for the Aroon Indicator.
    """
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14
    return period + 2

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    """
    return {
        "period": args[0] if len(args) > 0 else "14"
    }

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    try:
        period = int(options.get('period', 25))
    except (ValueError, TypeError):
        period = 25

    # 1. Create shifted columns for the window
    # Index 0 is 'now', Index 1 is '1 bar ago', etc.
    high_shifts = [pl.col("high").shift(i) for i in range(period + 1)]
    low_shifts = [pl.col("low").shift(i) for i in range(period + 1)]

    # 2. Concat into a list column and find the index of the max/min
    # .list.arg_max() returns the index in the list (0 to period)
    # This index corresponds exactly to "how many bars ago" the high occurred.
    
    days_since_high = pl.concat_list(high_shifts).list.arg_max()
    days_since_low = pl.concat_list(low_shifts).list.arg_min()

    # 3. Calculate Aroon
    aroon_up = (
        (period - days_since_high) / period * 100
    )

    aroon_down = (
        (period - days_since_low) / period * 100
    )

    return [
        aroon_up.alias(f"{indicator_str}__aroon_up"),
        aroon_down.alias(f"{indicator_str}__aroon_down")
    ]

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    Legacy Pandas fallback.
    """
    try:
        period = int(options.get('period', 25))
    except (ValueError, TypeError):
        period = 25

    # Window needs to include 'period' + current bar
    window = period + 1
    
    # Calculate rolling argmax (index of high/low within the window)
    # raw=True improves performance by using numpy arrays
    aroon_up_days = df['high'].rolling(window=window).apply(lambda x: x.argmax(), raw=True)
    aroon_down_days = df['low'].rolling(window=window).apply(lambda x: x.argmin(), raw=True)

    # Logic: If argmax is at the end (index == period), Aroon = 100.
    # If argmax is at the start (index == 0), Aroon = 0.
    res_up = (aroon_up_days / period) * 100
    res_down = (aroon_down_days / period) * 100

    return pd.DataFrame({
        'aroon_up': res_up,
        'aroon_down': res_down
    }, index=df.index)