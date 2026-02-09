import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "The Hurst Exponent is a statistical measure used to determine the long-term "
        "memory of price series. H > 0.5 is trending, H < 0.5 is mean-reverting, "
        "and H = 0.5 suggests a random walk."
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
        "polars": 0,
        "polars_input": 1
    }

def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for the Hurst Exponent.
    """
    try:
        period = int(options.get('period', 50))
    except (ValueError, TypeError):
        period = 50
    return period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    """
    return {
        "period": args[0] if len(args) > 0 else "50"
    }

def calculate(df: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    """
    High-performance Hurst Exponent implementation for polars_input: 1.
    Vectorizes the rescaled range / lag variance analysis across 1M rows.
    """
    try:
        period = int(options.get('period', 50))
    except (ValueError, TypeError):
        period = 50

    if len(df) < period:
        return pl.DataFrame({
            "hurst": [None] * len(df),
            "regime": [0.0] * len(df)
        }).with_columns([
            pl.col("hurst").cast(pl.Float64),
            pl.col("regime").cast(pl.Float64)
        ])

    close_v = df["close"].to_numpy()
    windows = np.lib.stride_tricks.sliding_window_view(close_v, window_shape=period)
    
    lags = np.unique(np.linspace(2, period // 2, 5).astype(int))
    log_lags = np.log(lags)
    
    log_taus = []
    
    for lag in lags:
        diffs = windows[:, lag:] - windows[:, :-lag]
        std_v = np.std(diffs, axis=1)
        std_v = np.where(std_v > 0, std_v, 1e-10)
        log_taus.append(np.log(np.sqrt(std_v)))

    log_taus = np.column_stack(log_taus)

    x = log_lags
    x_mean = np.mean(x)
    y_means = np.mean(log_taus, axis=1)[:, np.newaxis]
    
    numerator = np.sum((x - x_mean) * (log_taus - y_means), axis=1)
    denominator = np.sum((x - x_mean)**2)
    
    hurst_values = (numerator / denominator) * 2.0

    padding = np.full(period - 1, np.nan)
    full_hurst = np.concatenate([padding, hurst_values])

    res = pl.DataFrame({"hurst": full_hurst})

    res = res.with_columns(
        pl.when(pl.col("hurst") > 0.55).then(1.0)
        .when(pl.col("hurst") < 0.45).then(-1.0)
        .otherwise(0.0)
        .alias("regime")
    )

    return res