import pandas as pd
import numpy as np
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "Fractal Dimension (Sevcik method) quantifies the complexity and 'jaggedness' "
        "of price action to distinguish between trending and mean-reverting markets. "
        "A value near 1.0 indicates a smooth, strong trend, while values approaching "
        "2.0 suggest high complexity, noise, and turbulent market conditions. It helps "
        "traders determine whether to use trend-following or range-bound strategies."
    )

def meta()->Dict:
    """
    Any other metadata to pass via API
    """
    return {
        "author": "Google Gemini",
        "version": 1.0,
        "panel": 1,
        "verified": 1
    }
    
def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for Fractal Dimension.
    Requires a full 'period' to calculate the Sevcik dimension.
    We use 3x period for stability and consistency across the engine.
    """
    try:
        period = int(options.get('period', 30))
    except (ValueError, TypeError):
        period = 30

    # Consistent with other rolling-window stabilization buffers
    return period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: fractaldimension_30 -> {'period': '30'}
    """
    return {
        "period": args[0] if len(args) > 0 else "30"
    }

def get_sevcik_dimension(y: np.ndarray) -> float:
    """
    Vectorized Sevcik Fractal Dimension calculation for a price segment.
    """
    n = len(y)
    if n < 2:
        return 1.0
        
    y_min = np.min(y)
    y_max = np.max(y)
    
    # Handle flat periods to avoid division by zero
    if y_max == y_min:
        return 1.0
        
    # Normalize price to [0, 1]
    y_norm = (y - y_min) / (y_max - y_min)
    
    # Sum of Euclidean distances between successive normalized points
    # x-intervals are normalized as 1/(n-1)
    dist = np.sum(np.sqrt(np.diff(y_norm)**2 + (1.0 / (n - 1))**2))
    
    # Sevcik Formula
    return 1.0 + (np.log(dist) + np.log(2)) / np.log(2 * (n - 1))

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    High-performance vectorized Fractal Dimension calculation using Sevcik method.
    D < 1.3: Trending
    D > 1.6: Turbulent/Noise
    """
    # 1. Parse Parameters
    try:
        period = int(options.get('period', 30))
    except (ValueError, TypeError):
        period = 30

    # 2. Determine Precision (Standardizing output formatting)
    precision = 4

    # 3. Calculation Logic
    # Use rolling.apply with raw=True to pass a NumPy array to the Sevcik function
    # This is significantly faster than passing a Series
    fractal_dim = df['close'].rolling(window=period).apply(get_sevcik_dimension, raw=True)

    # 4. Market State Classification (Vectorized)
    # Replaces the previous .apply(lambda) with high-speed np.select
    conditions = [
        (fractal_dim < 1.3),
        (fractal_dim > 1.6)
    ]
    choices = ["Trending", "Turbulent/Noise"]
    market_state = np.select(conditions, choices, default="Transition")

    # 5. Final Formatting
    # Preserving the original index for O(1) merging in parallel.py
    res = pd.DataFrame({
        'fractal_dim': fractal_dim.round(precision),
        'market_state': market_state
    }, index=df.index)
    
    # Drop rows where the window hasn't filled (warm-up period)
    return res.dropna(subset=['fractal_dim'])