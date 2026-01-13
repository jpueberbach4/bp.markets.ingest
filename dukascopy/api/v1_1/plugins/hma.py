import pandas as pd
import numpy as np
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "The Hull Moving Average (HMA) is an extremely fast and smooth moving average "
        "designed to almost eliminate lag while simultaneously improving smoothing. "
        "It achieves this by using a weighted moving average of the difference between "
        "two other weighted moving averages with different periods, making it highly "
        "responsive to price activity while maintaining a smooth curve."
    )

def meta()->Dict:
    """
    Any other metadata to pass via API
    """
    return {
        "author": "Google Gemini",
        "version": 1.0
    }
    
def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for the Hull Moving Average.
    HMA requires a full 'period' for the initial WMA components, 
    plus additional rows for the final sqrt(period) smoothing.
    We use a 3x multiplier to ensure total stability.
    """
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14

    # The mathematical minimum is (period + sqrt(period)).
    # We use the 3x period standard to match SMA and EMA for visual consistency.
    return period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: hma_14 -> {'period': '14'}
    """
    return {
        "period": args[0] if len(args) > 0 else "14"
    }

def fast_wma(series: pd.Series, n: int) -> pd.Series:
    """
    High-performance vectorized WMA using NumPy strides.
    """
    if n < 1:
        return series
    
    weights = np.arange(1, n + 1)
    
    # Use sliding window view to apply weights across the series
    def rolling_window(a, window):
        shape = a.shape[:-1] + (a.shape[-1] - window + 1, window)
        strides = a.strides + (a.strides[-1],)
        return np.lib.stride_tricks.as_strided(a, shape=shape, strides=strides)

    values = series.values
    if len(values) < n:
        return pd.Series(np.nan, index=series.index)
        
    windows = rolling_window(values, n)
    # Calculate weighted average: (sum of values * weights) / sum of weights
    wma_values = np.dot(windows, weights) / weights.sum()
    
    # Lead with NaNs to match original series length
    result = np.empty(len(series))
    result.fill(np.nan)
    result[n-1:] = wma_values
    
    return pd.Series(result, index=series.index)

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    High-performance vectorized Hull Moving Average (HMA) calculation.
    Formula: WMA(2*WMA(n/2) - WMA(n), sqrt(n))
    """
    # 1. Parse Parameters
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14

    # 2. Determine Price Precision for rounding
    try:
        sample_price = str(df['close'].iloc[0])
        precision = len(sample_price.split('.')[1]) if '.' in sample_price else 2
    except (IndexError, AttributeError):
        precision = 5

    # 3. Calculation Logic
    half_period = int(period / 2)
    sqrt_period = int(np.sqrt(period))

    # A. Calculate the components: 2 * WMA(n/2) - WMA(n)
    wma_half = fast_wma(df['close'], half_period)
    wma_full = fast_wma(df['close'], period)
    
    raw_hma = (2 * wma_half) - wma_full
    
    # B. Final smoothing: WMA(raw_hma, sqrt(n))
    hma = fast_wma(raw_hma.dropna(), sqrt_period)

    # 4. Final Formatting and Rounding
    # Re-indexing to the original df to ensure O(1) join in parallel.py
    res = pd.DataFrame({
        'hma': hma.round(precision)
    }, index=df.index)
    
    # Drop rows where HMA hasn't stabilized (warm-up period)
    return res.dropna(subset=['hma'])