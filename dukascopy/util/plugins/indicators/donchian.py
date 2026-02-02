import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "Donchian Channels are a volatility indicator used to identify trend "
        "extremes and potential breakouts. It plots three lines: the Upper Band "
        "(highest price over the period), the Lower Band (lowest price over the "
        "period), and the Midline (average of the Upper and Lower bands)."
    )

def meta() -> Dict:
    """
    Metadata for the dual-engine orchestrator.
    """
    return {
        "author": "Google Gemini",
        "version": 1.1,
        "verified": 1,
        "polars": 1,  # Trigger high-speed Polars execution path
        "needs": "surface-colour"
    }

def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for Donchian Channels.
    """
    try:
        period = int(options.get('period', 20))
    except (ValueError, TypeError):
        period = 20
    return period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: donchian_20 -> {'period': '20'}
    """
    return {
        "period": args[0] if len(args) > 0 else "20"
    }

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    """
    High-performance Polars-native calculation using Lazy expressions.
    """
    try:
        period = int(options.get('period', 20))
    except (ValueError, TypeError):
        period = 20

    # 1. Define the rolling extremes
    # Polars uses highly optimized Rust kernels for rolling_max/min
    upper = pl.col("high").rolling_max(window_size=period)
    lower = pl.col("low").rolling_min(window_size=period)

    # 2. Derive the Midline
    mid = (upper + lower) / 2

    # 3. Return as a list of aliased expressions for the nested orchestrator
    # Using the __ prefix to trigger the dictionary grouping in parallel.py
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
    except (ValueError, TypeError):
        period = 20

    upper = df['high'].rolling(window=period).max()
    lower = df['low'].rolling(window=period).min()
    mid = (upper + lower) / 2

    return pd.DataFrame({
        'upper': upper,
        'mid': mid,
        'lower': lower
    }, index=df.index).dropna(subset=['upper'])