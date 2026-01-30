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
        "version": 1.1,
        "panel": 1,
        "verified": 1,
        "polars": 1  # Trigger high-speed Polars execution path
    }

def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for Fractal Dimension.
    """
    try:
        period = int(options.get('period', 30))
    except (ValueError, TypeError):
        period = 30
    return period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    """
    return {
        "period": args[0] if len(args) > 0 else "30"
    }

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    """
    High-performance Polars-native calculation using Sevcik method.
    """
    try:
        period = int(options.get('period', 30))
    except (ValueError, TypeError):
        period = 30

    def sevcik_logic(s: pl.Series) -> float:
        y = s.to_numpy()
        n = len(y)
        if n < 2: return 1.0
        y_min, y_max = np.min(y), np.max(y)
        if y_max == y_min: return 1.0
        
        y_norm = (y - y_min) / (y_max - y_min)
        dist = np.sum(np.sqrt(np.diff(y_norm)**2 + (1.0 / (n - 1))**2))
        return 1.0 + (np.log(dist) + np.log(2)) / np.log(2 * (n - 1))

    # Calculate Dimension
    fractal_dim = pl.col("close").rolling_map(sevcik_logic, window_size=period)

    # Market State Classification
    market_state = (
        pl.when(fractal_dim < 1.3).then(pl.lit("Trending"))
        .when(fractal_dim > 1.6).then(pl.lit("Turbulent/Noise"))
        .otherwise(pl.lit("Transition"))
    )

    return [
        fractal_dim.alias(f"{indicator_str}__fractal_dim"),
        market_state.alias(f"{indicator_str}__market_state")
    ]

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    Legacy Pandas fallback using the optimized NumPy logic.
    """
    try:
        period = int(options.get('period', 30))
    except (ValueError, TypeError):
        period = 30

    def get_sevcik_dimension(y):
        n = len(y)
        if n < 2: return 1.0
        y_min, y_max = np.min(y), np.max(y)
        if y_max == y_min: return 1.0
        y_norm = (y - y_min) / (y_max - y_min)
        dist = np.sum(np.sqrt(np.diff(y_norm)**2 + (1.0 / (n - 1))**2))
        return 1.0 + (np.log(dist) + np.log(2)) / np.log(2 * (n - 1))

    fractal_dim = df['close'].rolling(window=period).apply(get_sevcik_dimension, raw=True)
    
    conditions = [(fractal_dim < 1.3), (fractal_dim > 1.6)]
    choices = ["Trending", "Turbulent/Noise"]
    market_state = np.select(conditions, choices, default="Transition")

    return pd.DataFrame({
        'fractal_dim': fractal_dim,
        'market_state': market_state
    }, index=df.index).dropna(subset=['fractal_dim'])