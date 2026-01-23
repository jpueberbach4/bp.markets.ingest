import pandas as pd
import numpy as np
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

def meta()->Dict:
    """
    Any other metadata to pass via API
    """
    return {
        "author": "Google Gemini",
        "version": 1.0,
        "verified": 1
    }
     
def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for Linear Regression Channels.
    Requires a full 'period' to calculate the slope, intercept, and 
    maximum deviation. We use 3x period for stability.
    """
    try:
        period = int(options.get('period', 50))
    except (ValueError, TypeError):
        period = 50

    # Consistent with other rolling-window stabilization buffers
    return period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: linregchannel_50 -> {'period': '50'}
    """
    return {
        "period": args[0] if len(args) > 0 else "50"
    }

def get_linreg_stats(y: np.ndarray):
    """
    Calculates the endpoint of a linear regression line and 
    the maximum absolute deviation (width) for a price segment.
    """
    x = np.arange(len(y))
    # Fit line: y = mx + c
    slope, intercept = np.polyfit(x, y, 1)
    
    # Calculate the value of the line at the current (last) point
    mid_point = slope * (len(y) - 1) + intercept
    
    # Calculate the regression line for the whole segment to find max deviation
    line = slope * x + intercept
    width = np.max(np.abs(y - line))
    
    return mid_point, width

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    High-performance vectorized Linear Regression Channel calculation.
    """
    # 1. Parse Parameters
    try:
        period = int(options.get('period', 50))
    except (ValueError, TypeError):
        period = 50

    # 2. Determine Price Precision
    try:
        sample_price = str(df['close'].iloc[0])
        precision = len(sample_price.split('.')[1])+1 if '.' in sample_price else 2
    except (IndexError, AttributeError):
        precision = 5

    # 3. Calculation Logic
    # We use a custom rolling apply that returns both mid and width
    # Using raw=True for NumPy speed
    res_raw = df['close'].rolling(window=period).apply(
        lambda x: get_linreg_stats(x)[0], raw=True
    )
    
    width_raw = df['close'].rolling(window=period).apply(
        lambda x: get_linreg_stats(x)[1], raw=True
    )

    # 4. Generate Channels
    lin_mid = res_raw
    lin_upper = lin_mid + width_raw
    lin_lower = lin_mid - width_raw

    # 5. Final Formatting and Rounding
    # Preserving the original index for O(1) merging in parallel.py
    res = pd.DataFrame({
        'lin_mid': lin_mid.round(precision),
        'lin_upper': lin_upper.round(precision),
        'lin_lower': lin_lower.round(precision)
    }, index=df.index)
    
    # Drop rows where the window hasn't filled (warm-up period)
    return res.dropna(subset=['lin_mid'])