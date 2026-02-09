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
        "polars": 0,
        "polars_input": 1
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

def calculate(df: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    """
    High-performance vectorized Aroon calculation using Numpy sliding windows.
    Supports polars_input: 1
    """
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14

    window_size = period + 1

    if len(df) < window_size:
        return pl.DataFrame({
            "aroon_down": [None] * len(df),
            "aroon_up": [None] * len(df)
        }).with_columns([
            pl.col("aroon_down").cast(pl.Float64),
            pl.col("aroon_up").cast(pl.Float64)
        ])

    high_v = df["high"].to_numpy()
    low_v = df["low"].to_numpy()

    high_windows = np.lib.stride_tricks.sliding_window_view(high_v, window_shape=window_size)
    low_windows = np.lib.stride_tricks.sliding_window_view(low_v, window_shape=window_size)

    arg_max = np.argmax(high_windows, axis=1)
    arg_min = np.argmin(low_windows, axis=1)

    aroon_up = (arg_max / period) * 100
    aroon_down = (arg_min / period) * 100

    pad_size = window_size - 1
    padding = np.full(pad_size, np.nan)
    
    final_up = np.concatenate([padding, aroon_up])
    final_down = np.concatenate([padding, aroon_down])

    # 6. Return Polars DataFrame
    return pl.DataFrame({
        "aroon_down": final_down,
        "aroon_up": final_up
    })