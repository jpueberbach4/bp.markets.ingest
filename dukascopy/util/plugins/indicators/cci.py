import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "Commodity Channel Index (CCI) measures the current price level relative "
        "to an average price level over a given period. It is used to identify "
        "new trends or warn of extreme overbought/oversold conditions."
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
        "polars": 0,
        "polars_input":1 
    }

def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for CCI.
    """
    try:
        period = int(options.get('period', 20))
    except (ValueError, TypeError):
        period = 20
    return period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    """
    return {
        "period": args[0] if len(args) > 0 else "20"
    }

def calculate(df: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    """
    High-performance vectorized implementation using Numpy sliding window views.
    This eliminates the UDF overhead entirely.
    """
    try:
        period = int(options.get('period', 20))
    except (ValueError, TypeError):
        period = 20

    if len(df) < period:
        return pl.DataFrame({
            "cci": [None] * len(df),
            "direction": [None] * len(df)
        }).with_columns([
            pl.col("cci").cast(pl.Float64),
            pl.col("direction").cast(pl.Int32)
        ])

    tp = (df["high"] + df["low"] + df["close"]) / 3
    tp_v = tp.to_numpy()

    windows = np.lib.stride_tricks.sliding_window_view(tp_v, window_shape=period)

    means = np.mean(windows, axis=1)
    mads = np.mean(np.abs(windows - means[:, None]), axis=1)

    padding = np.full(period - 1, np.nan)
    full_means = np.concatenate([padding, means])
    full_mads = np.concatenate([padding, mads])

    cci_values = (tp_v - full_means) / (0.015 * full_mads + 1e-12)

    res = pl.DataFrame({"cci": cci_values})
    
    res = res.with_columns(
        pl.when(pl.col("cci") > pl.col("cci").shift(1))
        .then(100)
        .otherwise(-100)
        .alias("direction")
    ).cast({"direction": pl.Int32})

    return res