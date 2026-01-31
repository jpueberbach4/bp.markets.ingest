import polars as pl
import pandas as pd
import numpy as np
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "The Stochastic Oscillator is a momentum indicator that compares a specific "
        "closing price of an asset to a range of its prices over a certain period of "
        "time. It consists of two lines: %K (the fast line) and %D (the 3-period "
        "moving average of %K). The indicator oscillates between 0 and 100, where "
        "readings above 80 signal overbought conditions and readings below 20 "
        "indicate oversold conditions."
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
        "polars": 1  # Flag to trigger high-speed Polars execution
    }

def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for the Stochastic Oscillator.
    """
    try:
        k_period = int(options.get('k_period', 14))
    except (ValueError, TypeError):
        k_period = 14
    return k_period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: stochastic_14_3 -> {'k_period': '14', 'd_period': '3'}
    """
    return {
        "k_period": args[0] if len(args) > 0 else "14",
        "d_period": args[1] if len(args) > 1 else "3"
    }

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    """
    High-performance Polars-native calculation for Stochastic Oscillator.
    """
    try:
        k_period = int(options.get('k_period', 14))
        d_period = int(options.get('d_period', 3))
    except (ValueError, TypeError):
        k_period, d_period = 14, 3

    # 1. Rolling Low and High over the k_period
    low_min = pl.col("low").rolling_min(window_size=k_period)
    high_max = pl.col("high").rolling_max(window_size=k_period)
    
    # 2. Calculate %K (Fast Line)
    # Handle division by zero for flat price action by filling nulls/NaNs with 50 (neutral)
    denom = high_max - low_min
    stoch_k = (100 * (pl.col("close") - low_min) / denom).fill_nan(50).fill_null(50)
    
    # 3. Calculate %D (Slow Line - SMA of %K)
    stoch_d = stoch_k.rolling_mean(window_size=d_period)

    # 4. Return as aliased expressions for structural nesting
    return [
        stoch_k.round(2).alias(f"{indicator_str}__stoch_k"),
        stoch_d.round(2).alias(f"{indicator_str}__stoch_d")
    ]

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    Legacy fallback for Pandas-only environments.
    """
    try:
        k_period = int(options.get('k_period', 14))
        d_period = int(options.get('d_period', 3))
    except (ValueError, TypeError):
        k_period, d_period = 14, 3

    precision = 2 

    low_min = df['low'].rolling(window=k_period).min()
    high_max = df['high'].rolling(window=k_period).max()
    
    denom = (high_max - low_min).replace(0, np.nan)
    stoch_k = 100 * (df['close'] - low_min) / denom
    
    stoch_d = stoch_k.rolling(window=d_period).mean()

    res = pd.DataFrame({
        'stoch_k': stoch_k.round(precision),
        'stoch_d': stoch_d.round(precision)
    }, index=df.index)
    
    return res.dropna(subset=['stoch_d'])