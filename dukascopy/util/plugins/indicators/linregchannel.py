import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "Linear Regression Channels use a mathematical 'best-fit' line to identify "
        "the center of a price trend. The indicator consists of three lines: the "
        "Median Line (a linear regression line), and Upper and Lower Channels based "
        "on the maximum price deviation from that line over a set period. It is "
        "highly effective for identifying trend exhaustion and potential price "
        "reversals when price touches the outer channel boundaries."
    )

def meta() -> Dict:
    """
    Metadata for the dual-engine orchestrator.
    """
    return {
        "author": "Google Gemini",
        "version": 1.1,
        "verified": 1,
        "polars": 0,
        "polars_input": 1
    }

def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for Linear Regression Channels.
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
    High-performance Linear Regression Channel for polars_input: 1.
    Vectorizes slope, intercept, and max-deviation width across 1M rows.
    """
    try:
        period = int(options.get('period', 50))
    except (ValueError, TypeError):
        period = 50

    if len(df) < period:
        return pl.DataFrame({
            "lin_mid": [None] * len(df),
            "lin_upper": [None] * len(df),
            "lin_lower": [None] * len(df)
        }).with_columns([pl.all().cast(pl.Float64)])

    y = df["close"].to_numpy()
    windows = np.lib.stride_tricks.sliding_window_view(y, window_shape=period)
    
    x = np.arange(period)
    x_mean = np.mean(x)
    y_means = np.mean(windows, axis=1)[:, np.newaxis]
    
    x_diff = x - x_mean
    numerator = np.sum(x_diff * (windows - y_means), axis=1)
    denominator = np.sum(x_diff**2)
    slopes = numerator / denominator
    
    intercepts = y_means.flatten() - slopes * x_mean
    
    mid_points = slopes * (period - 1) + intercepts
    
    full_lines = slopes[:, np.newaxis] * x + intercepts[:, np.newaxis]
    widths = np.max(np.abs(windows - full_lines), axis=1)

    padding = np.full(period - 1, np.nan)
    
    lin_mid = np.concatenate([padding, mid_points])
    width_v = np.concatenate([padding, widths])
    
    lin_upper = lin_mid + width_v
    lin_lower = lin_mid - width_v

    # 6. Return as Polars DataFrame
    return pl.DataFrame({
        "lin_mid": lin_mid,
        "lin_upper": lin_upper,
        "lin_lower": lin_lower
    })