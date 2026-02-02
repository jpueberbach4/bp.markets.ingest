import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "Bollinger Bands (BBands) are a volatility indicator consisting of a "
        "Simple Moving Average (mid) and two standard deviation lines (upper and lower). "
        "They expand during high volatility and contract during low volatility."
    )

def meta() -> Dict:
    """
    Metadata for the dual-engine orchestrator.
    """
    return {
        "author": "Google Gemini",
        "version": 1.1,
        "panel": 0,
        "verified": 1,
        "polars": 1  # Trigger high-speed Polars execution path
    }

def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for Bollinger Bands.
    """
    try:
        period = int(options.get('period', 20))
    except (ValueError, TypeError):
        period = 20
    return period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: bbands_20_2 -> {'period': '20', 'std': '2.0'}
    """
    return {
        "period": args[0] if len(args) > 0 else "20",
        "std": args[1] if len(args) > 1 else "2.0"
    }

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    """
    High-performance Polars-native calculation using Lazy expressions.
    """
    try:
        period = int(options.get('period', 20))
        std_dev = float(options.get('std', 2.0))
    except (ValueError, TypeError):
        period, std_dev = 20, 2.0

    # 1. Define the base rolling components
    # Polars optimizes these to run in a single pass over the 'close' column
    mid = pl.col("close").rolling_mean(window_size=period)
    std = pl.col("close").rolling_std(window_size=period)

    # 2. Calculate Upper and Lower bands
    upper = mid + (std * std_dev)
    lower = mid - (std * std_dev)

    # 3. Return as a list of aliased expressions
    # Using the __ prefix for the nested dictionary logic in parallel.py
    return [
        upper.alias(f"{indicator_str}__upper"),
        mid.alias(f"{indicator_str}__mid"),
        lower.alias(f"{indicator_str}__lower")
    ]

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    Legacy Pandas fallback.
    """
    try:
        period = int(options.get('period', 20))
        std_dev = float(options.get('std', 2.0))
    except (ValueError, TypeError):
        period, std_dev = 20, 2.0

    mid = df['close'].rolling(window=period).mean()
    rolling_std = df['close'].rolling(window=period).std()
    
    upper = mid + (rolling_std * std_dev)
    lower = mid - (rolling_std * std_dev)

    return pd.DataFrame({
        'upper': upper,
        'mid': mid,
        'lower': lower
    }, index=df.index).dropna()