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
        "polars": 1     # Now fixed and enabled for high-speed execution
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

def get_sevcik_dimension(y: np.ndarray) -> float:
    """
    Vectorized Sevcik Fractal Dimension calculation.
    """
    n = len(y)
    if n < 2: return 1.0
    y_min, y_max = np.min(y), np.max(y)
    if y_max == y_min: return 1.0
    
    # Normalize price to [0, 1]
    y_norm = (y - y_min) / (y_max - y_min)
    
    # Euclidean distance of normalized path inside a unit square
    dist = np.sum(np.sqrt(np.diff(y_norm)**2 + (1.0 / (n - 1))**2))
    
    return 1.0 + (np.log(dist) + np.log(2)) / np.log(2 * (n - 1))

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    """
    High-performance Polars-native calculation using Sevcik method.
    Fixes the 'round' crash by separating numeric and string expressions.
    """
    try:
        period = int(options.get('period', 30))
    except (ValueError, TypeError):
        period = 30

    # 1. Dimension Calculation (using map_batches/rolling_map for the recursive math)
    # We cast to Float64 immediately to prevent type panics
    fractal_dim = pl.col("close").cast(pl.Float64).rolling_map(
        lambda s: get_sevcik_dimension(s.to_numpy()), 
        window_size=period
    )

    # 2. Market State Classification (Native Polars)
    market_state = (
        pl.when(fractal_dim < 1.3).then(pl.lit("Trending"))
        .when(fractal_dim > 1.6).then(pl.lit("Turbulent/Noise"))
        .otherwise(pl.lit("Transition"))
    )

    # 3. Return expressions. We round the numeric one here to satisfy the engine
    return [
        fractal_dim.round(4).alias(f"{indicator_str}__fractal_dim"),
        market_state.alias(f"{indicator_str}__market_state")
    ]

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    Pandas fallback. Handles precision locally to avoid engine-level rounding errors.
    """
    try:
        period = int(options.get('period', 30))
    except (ValueError, TypeError):
        period = 30

    # raw=True ensures we pass a high-speed NumPy array to the worker
    fractal_dim = df['close'].rolling(window=period).apply(get_sevcik_dimension, raw=True)

    conditions = [ (fractal_dim < 1.3), (fractal_dim > 1.6) ]
    choices = ["Trending", "Turbulent/Noise"]
    market_state = np.select(conditions, choices, default="Transition")

    res = pd.DataFrame({
        'fractal_dim': fractal_dim.round(4),
        'market_state': market_state.astype(str)
    }, index=df.index)
    
    return res.dropna(subset=['fractal_dim'])