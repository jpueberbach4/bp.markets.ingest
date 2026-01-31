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
        "polars": 1  # Flag to trigger high-speed Polars execution
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

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    """
    High-performance Polars-native calculation using rolling regression.
    """
    try:
        period = int(options.get('period', 50))
    except (ValueError, TypeError):
        period = 50

    # 1. Rolling Linear Regression to get Median Line
    # We use a rolling window to solve y = mx + c for the last point
    # Polars optimized rolling_map handles the segment-based polyfit logic efficiently
    mid = pl.col("close").rolling_map(
        lambda s: np.polyfit(np.arange(len(s)), s.to_numpy(), 1).dot([len(s) - 1, 1]),
        window_size=period
    )

    # 2. Maximum Deviation (Width)
    # To find max absolute deviation, we compute the full line within the window
    # and find the max(abs(price - line))
    def get_max_dev(s):
        y = s.to_numpy()
        x = np.arange(len(y))
        slope, intercept = np.polyfit(x, y, 1)
        line = slope * x + intercept
        return np.max(np.abs(y - line))

    width = pl.col("close").rolling_map(get_max_dev, window_size=period)

    # 3. Channel Construction
    upper = mid + width
    lower = mid - width

    return [
        upper.round(5).alias(f"{indicator_str}__lin_upper"),
        mid.round(5).alias(f"{indicator_str}__lin_mid"),
        lower.round(5).alias(f"{indicator_str}__lin_lower")
    ]

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    Legacy fallback for Pandas-only environments.
    """
    try:
        period = int(options.get('period', 50))
    except (ValueError, TypeError):
        period = 50

    try:
        sample_price = str(df['close'].iloc[0])
        precision = len(sample_price.split('.')[1])+1 if '.' in sample_price else 2
    except (IndexError, AttributeError):
        precision = 5

    def get_linreg_stats(y: np.ndarray):
        x = np.arange(len(y))
        slope, intercept = np.polyfit(x, y, 1)
        mid_point = slope * (len(y) - 1) + intercept
        line = slope * x + intercept
        width = np.max(np.abs(y - line))
        return mid_point, width

    res_raw = df['close'].rolling(window=period).apply(
        lambda x: get_linreg_stats(x)[0], raw=True
    )
    
    width_raw = df['close'].rolling(window=period).apply(
        lambda x: get_linreg_stats(x)[1], raw=True
    )

    lin_mid = res_raw
    lin_upper = lin_mid + width_raw
    lin_lower = lin_mid - width_raw

    res = pd.DataFrame({
        'lin_mid': lin_mid.round(precision),
        'lin_upper': lin_upper.round(precision),
        'lin_lower': lin_lower.round(precision)
    }, index=df.index)
    
    return res.dropna(subset=['lin_mid'])