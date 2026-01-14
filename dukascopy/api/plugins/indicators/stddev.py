import pandas as pd
import numpy as np
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "Standard Deviation is a statistical measure of market volatility. It "
        "quantifies the amount of variation or dispersion of price data points "
        "from their moving average. High values indicate that prices are spread "
        "out over a wider range (high volatility), while low values indicate "
        "that price is consolidating closely around its average (low volatility)."
    )

def meta()->Dict:
    """
    Any other metadata to pass via API
    """
    return {
        "author": "Google Gemini",
        "version": 1.0,
        "panel": 1
    }
    
def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for Standard Deviation.
    Requires a full 'period' to calculate the initial mean and variance.
    We use 3x period for stability and engine consistency.
    """
    try:
        period = int(options.get('period', 20))
    except (ValueError, TypeError):
        period = 20

    # Consistent with other rolling-window stabilization buffers
    return period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: stddev_20 -> {'period': '20'}
    """
    return {
        "period": args[0] if len(args) > 0 else "20"
    }

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    High-performance vectorized Standard Deviation calculation.
    Measures the dispersion of prices from their moving average.
    """
    # 1. Parse Parameters
    try:
        period = int(options.get('period', 20))
    except (ValueError, TypeError):
        period = 20

    # 2. Determine Price Precision
    try:
        sample_price = str(df['close'].iloc[0])
        precision = len(sample_price.split('.')[1]) if '.' in sample_price else 2
    except (IndexError, AttributeError):
        precision = 5

    # 3. Vectorized Calculation Logic
    # Calculates rolling standard deviation using C-level optimizations
    std_dev = df['close'].rolling(window=period).std()

    # 4. Final Formatting and Rounding
    # Preserving the original index for O(1) merging in parallel.py
    res = pd.DataFrame({
        'std_dev': std_dev.round(precision)
    }, index=df.index)
    
    # Drop rows where the window hasn't filled (warm-up period)
    return res.dropna(subset=['std_dev'])