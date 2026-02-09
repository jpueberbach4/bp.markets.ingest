import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "Fractal Dimension (Sevcik method) quantifies the complexity and 'jaggedness' "
        "of price action to distinguish between trending and mean-reverting markets. "
        "Values near 1.0 indicate a smooth trend; values near 2.0 suggest noise."
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
    try:
        period = int(options.get('period', 30))
    except (ValueError, TypeError):
        period = 30
    return period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "period": args[0] if len(args) > 0 else "30"
    }

def calculate(df: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    """
    High-performance Sevcik Fractal Dimension implementation for polars_input: 1.
    Vectorizes windowed normalization and logarithmic scaling via Numpy views.
    """
    try:
        period = int(options.get('period', 30))
    except (ValueError, TypeError):
        period = 30

    if len(df) < period:
        return pl.DataFrame({
            "fractal_dim": [None] * len(df),
            "market_state": ["Transition"] * len(df)
        }).with_columns([
            pl.col("fractal_dim").cast(pl.Float64),
            pl.col("market_state").cast(pl.Utf8)
        ])

    close_v = df["close"].to_numpy()
    windows = np.lib.stride_tricks.sliding_window_view(close_v, window_shape=period)
    
    y_min = np.min(windows, axis=1)[:, np.newaxis]
    y_max = np.max(windows, axis=1)[:, np.newaxis]
    
    range_v = y_max - y_min
    range_v = np.where(range_v == 0, 1.0, range_v)
    
    y_norm = (windows - y_min) / range_v

    diffs_sq = np.diff(y_norm, axis=1)**2
    step_sq = (1.0 / (period - 1))**2
    
    dist_sum = np.sum(np.sqrt(diffs_sq + step_sq), axis=1)

    fd_values = 1.0 + (np.log(dist_sum) + np.log(2)) / np.log(2 * (period - 1))

    padding = np.full(period - 1, np.nan)
    full_fd = np.concatenate([padding, fd_values])

    res = pl.DataFrame({"fractal_dim": full_fd.round(4)})

    res = res.with_columns(
        pl.when(pl.col("fractal_dim") < 1.3).then(pl.lit("Trending"))
        .when(pl.col("fractal_dim") > 1.6).then(pl.lit("Turbulent/Noise"))
        .otherwise(pl.lit("Transition"))
        .alias("market_state")
    )

    return res