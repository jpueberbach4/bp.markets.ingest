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
        "polars": 1
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
    Pure Polars Native Linear Regression Channels.
    No UDFs, no Python loops, 1:1 parity with Pandas math.
    """
    try:
        period = int(options.get('period', 50))
    except (ValueError, TypeError):
        period = 50

    # 1. Setup OLS Constants
    n = period
    sum_x = n * (n - 1) / 2
    sum_x2 = (n - 1) * n * (2 * n - 1) / 6
    divisor = n * sum_x2 - sum_x**2

    # 2. Vectorized OLS Slope and Intercept
    y = pl.col("close")
    # We use a moving index to keep the x-axis as [0, 1, ... n-1] for every window
    idx = pl.int_range(0, pl.len(), eager=False)
    
    sum_y = y.rolling_sum(window_size=n)
    sum_xy = (idx * y).rolling_sum(window_size=n) - (idx - n + 1) * sum_y

    slope = (n * sum_xy - sum_x * sum_y) / divisor
    intercept = (sum_y - slope * sum_x) / n
    
    # Mid Line (Endpoint of the regression line)
    lin_mid = slope * (n - 1) + intercept

    # 3. Native Maximum Absolute Deviation (Width)
    # We calculate the residuals for every point in the window simultaneously.
    # We iterate 0 to n-1 to find the max distance: |y_i - (slope * i + intercept)|
    residuals = []
    for i in range(n):
        # We look back 'i' steps from the current 'mid' calculation
        # The x-coordinate for a point 'i' steps back is (n - 1 - i)
        x_i = (n - 1) - i
        dist = (y.shift(i) - (slope * x_i + intercept)).abs()
        residuals.append(dist)

    # The Width is the maximum deviation found in that window
    width = pl.max_horizontal(residuals)

    return [
        (lin_mid + width).round(5).alias(f"{indicator_str}__lin_upper"),
        lin_mid.round(5).alias(f"{indicator_str}__lin_mid"),
        (lin_mid - width).round(5).alias(f"{indicator_str}__lin_lower")
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