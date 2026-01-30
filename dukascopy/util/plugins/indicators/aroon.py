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
        "polars": 1  # Trigger high-speed Polars execution path
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
    """
    High-performance Polars-native calculation for Aroon.
    """
    try:
        period = int(options.get('period', 25))
    except (ValueError, TypeError):
        period = 25

    # Window size includes the current bar
    window = period + 1

    # Calculation: ((period - days_since_extreme) / period) * 100
    # In Polars, we find the index of the max/min in the rolling window.
    # We use arg_max/arg_min within a rolling context.
    
    aroon_up = (
        pl.col("high")
        .rolling_map(lambda s: s.arg_max(), window_size=window) / period * 100
    )
    
    aroon_down = (
        pl.col("low")
        .rolling_map(lambda s: s.arg_min(), window_size=window) / period * 100
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

    window = period + 1
    
    # Standard Pandas rolling apply (slow)
    aroon_up_days = df['high'].rolling(window=window).apply(lambda x: x.argmax(), raw=True)
    aroon_down_days = df['low'].rolling(window=window).apply(lambda x: x.argmin(), raw=True)

    res_up = (aroon_up_days / period) * 100
    res_down = (aroon_down_days / period) * 100

    return pd.DataFrame({
        'aroon_up': res_up,
        'aroon_down': res_down
    }, index=df.index).dropna()