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
        "strength of that trend. It consists of 'Aroon Down' (measuring time "
        "since lowest low) and 'Aroon Up' (measuring time since highest high)."
    )

def meta() -> Dict:
    """
    Metadata for the dual-engine orchestrator.
    """
    return {
        "author": "Google Gemini",
        "version": 1.2, 
        "panel": 1,
        "verified": 1,
        "talib-validated": 1, 
        "polars": 1
    }

def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for the Aroon Indicator.
    """
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14
    return period + 1

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    """
    return {
        "period": args[0] if len(args) > 0 else "14"
    }

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14

    high_shifts = [pl.col("high").shift(i) for i in range(period + 1)]
    low_shifts = [pl.col("low").shift(i) for i in range(period + 1)]

    days_since_high = pl.concat_list(high_shifts).list.arg_max()
    days_since_low = pl.concat_list(low_shifts).list.arg_min()

    aroon_up = (
        (period - days_since_high) / period * 100
    )

    aroon_down = (
        (period - days_since_low) / period * 100
    )

    return [
        aroon_down.alias(f"{indicator_str}__aroon_down"),
        aroon_up.alias(f"{indicator_str}__aroon_up")
    ]

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    Legacy Pandas fallback.
    """
    try:
        # FIX 1: Default period matched to 14
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14

    window = period + 1
       
    aroon_up_days = df['high'].rolling(window=window).apply(lambda x: x.argmax(), raw=True)
    aroon_down_days = df['low'].rolling(window=window).apply(lambda x: x.argmin(), raw=True)

    res_up = (aroon_up_days / period) * 100
    res_down = (aroon_down_days / period) * 100

    return pd.DataFrame({
        'aroon_down': res_down,
        'aroon_up': res_up
    }, index=df.index)