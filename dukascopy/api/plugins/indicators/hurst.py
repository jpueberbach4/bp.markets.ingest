import pandas as pd
import numpy as np
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "The Hurst Exponent is a statistical measure used to determine the long-term "
        "memory of price series. It classifies market regimes: a value of 0.5 suggests "
        "a random walk (Brownian motion), values above 0.5 indicate a trending "
        "(persistent) market, and values below 0.5 indicate a mean-reverting "
        "(anti-persistent) market. It helps traders choose between trend-following "
        "and mean-reversion strategies."
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
    Calculates the required warmup rows for the Hurst Exponent.
    Requires a full 'period' to perform the rescaled range analysis.
    We use 3x period for statistical stability and engine consistency.
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
    Example: hurst_100 -> {'period': '100'}
    """
    return {
        "period": args[0] if len(args) > 0 else "50"
    }

def get_hurst_exponent(series: np.ndarray) -> float:
    """
    NumPy-accelerated calculation of the Hurst Exponent.
    Uses the rescaled range (R/S) approach.
    """
    n = len(series)
    if n < 10:  # Minimum statistical requirement
        return 0.5
        
    lags = range(2, n // 2)
    # Calculate the variance of the differences for each lag
    tau = [np.sqrt(np.std(np.subtract(series[lag:], series[:-lag]))) for lag in lags]
    
    # Avoid log of zero issues
    tau = [t if t > 0 else 1e-10 for t in tau]
    
    # Calculate the slope of the log-log plot (Hurst = slope * 2)
    poly = np.polyfit(np.log(lags), np.log(tau), 1)
    return float(poly[0] * 2.0)

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    High-performance vectorized Hurst Exponent calculation.
    H > 0.5: Trending (Persistent)
    H < 0.5: Mean-reverting (Anti-persistent)
    H = 0.5: Random Walk
    """
    # 1. Parse Parameters
    try:
        period = int(options.get('period', 50))
    except (ValueError, TypeError):
        period = 50

    # 2. Determine Precision
    precision = 4

    # 3. Calculation Logic
    # Using rolling().apply with raw=True for NumPy speed
    hurst = df['close'].rolling(window=period).apply(get_hurst_exponent, raw=True)

    # 4. Market Regime Classification (Vectorized)
    # Using np.select for high-speed labeling
    conditions = [
        (hurst > 0.55),
        (hurst < 0.45)
    ]
    choices = ["Trending", "Mean-Reverting"]
    regime = np.select(conditions, choices, default="Random")

    # 5. Final Formatting and Rounding
    # Preserving the original index for O(1) merging in parallel.py
    res = pd.DataFrame({
        'hurst': hurst.round(precision),
        'regime': regime
    }, index=df.index)
    
    # Drop rows where the window hasn't filled (warm-up period)
    return res.dropna(subset=['hurst'])