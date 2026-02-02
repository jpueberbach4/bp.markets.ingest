import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "The Hurst Exponent is a statistical measure used to determine the long-term "
        "memory of price series. H > 0.5 is trending, H < 0.5 is mean-reverting, "
        "and H = 0.5 suggests a random walk."
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
        "polars": 1  # Set to 1 to enable Polars path
    }

def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for the Hurst Exponent.
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
    High-performance Polars-native calculation for Hurst Exponent.
    """
    try:
        period = int(options.get('period', 50))
    except (ValueError, TypeError):
        period = 50

    def hurst_logic(s: pl.Series) -> float:
        series = s.to_numpy()
        n = len(series)
        if n < 10: return 0.5
        
        lags = range(2, n // 2)
        tau = [np.sqrt(np.std(series[lag:] - series[:-lag])) for lag in lags]
        tau = [t if t > 0 else 1e-10 for t in tau]
        
        poly = np.polyfit(np.log(lags), np.log(tau), 1)
        return float(poly[0] * 2.0)

    # Calculate Rolling Hurst Exponent
    hurst = pl.col("close").rolling_map(hurst_logic, window_size=period)

    # FIX: Use numeric codes to avoid float conversion errors in the engine
    # 1.0 = Trending, -1.0 = Mean-Reverting, 0.0 = Random
    regime = (
        pl.when(hurst > 0.55).then(1.0)
        .when(hurst < 0.45).then(-1.0)
        .otherwise(0.0)
    )

    return [
        hurst.alias(f"{indicator_str}__hurst"),
        regime.alias(f"{indicator_str}__regime")
    ]

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    Legacy Pandas fallback with numeric codes.
    """
    try:
        period = int(options.get('period', 50))
    except (ValueError, TypeError):
        period = 50

    def get_hurst_exponent(series):
        n = len(series)
        if n < 10: return 0.5
        lags = range(2, n // 2)
        tau = [np.sqrt(np.std(series[lag:] - series[:-lag])) for lag in lags]
        tau = [t if t > 0 else 1e-10 for t in tau]
        poly = np.polyfit(np.log(lags), np.log(tau), 1)
        return float(poly[0] * 2.0)

    hurst = df['close'].rolling(window=period).apply(get_hurst_exponent, raw=True)
    
    # FIX: Use float choices for Pandas/NumPy selection
    conditions = [(hurst > 0.55), (hurst < 0.45)]
    choices = [1.0, -1.0] 
    regime = np.select(conditions, choices, default=0.0)

    return pd.DataFrame({
        'hurst': hurst,
        'regime': regime
    }, index=df.index).dropna(subset=['hurst'])