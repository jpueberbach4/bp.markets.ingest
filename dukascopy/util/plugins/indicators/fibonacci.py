import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "Fibonacci Retracements identify potential support and resistance levels "
        "based on the golden ratio. It calculates horizontal lines at key levels "
        "(23.6%, 38.2%, 50%, 61.8%, and 78.6%) between the highest high and lowest low."
    )

def meta() -> Dict:
    """
    Metadata for the dual-engine orchestrator.
    """
    return {
        "author": "Google Gemini",
        "version": 1.1,
        "verified": 1,
        "polars": 1,
        "needs": "extension"
    }

def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for Fibonacci Retracements.
    """
    try:
        period = int(options.get('period', 100))
    except (ValueError, TypeError):
        period = 100
    return period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: fibonacci_100 -> {'period': '100'}
    """
    return {
        "period": args[0] if len(args) > 0 else "100"
    }

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    """
    High-performance Polars-native calculation for Fibonacci levels and extensions.
    """
    try:
        period = int(options.get('period', 100))
    except (ValueError, TypeError):
        period = 100

    hh = pl.col("high").rolling_max(window_size=period)
    ll = pl.col("low").rolling_min(window_size=period)
    diff = hh - ll

    return [
        # --- Standard Retracements ---
        hh.alias(f"{indicator_str}__fib_0"),
        (hh - (0.236 * diff)).alias(f"{indicator_str}__fib_236"),
        (hh - (0.382 * diff)).alias(f"{indicator_str}__fib_382"),
        (hh - (0.500 * diff)).alias(f"{indicator_str}__fib_50"),
        (hh - (0.618 * diff)).alias(f"{indicator_str}__fib_618"),
        (hh - (0.786 * diff)).alias(f"{indicator_str}__fib_786"),
        ll.alias(f"{indicator_str}__fib_100"),

        # --- Fibonacci Extensions (Price Targets) ---
        # Projects targets above the current range
        (hh + (0.272 * diff)).alias(f"{indicator_str}__ext_1272"),
        (hh + (0.618 * diff)).alias(f"{indicator_str}__ext_1618"),
        (hh + (1.618 * diff)).alias(f"{indicator_str}__ext_2618"),
        
        # Projects targets below the current range (for shorts)
        (ll - (0.272 * diff)).alias(f"{indicator_str}__ext_neg_1272"),
        (ll - (0.618 * diff)).alias(f"{indicator_str}__ext_neg_1618")
    ]

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    Legacy Pandas fallback.
    Updated to include Fibonacci Extensions for price targets.
    """
    try:
        period = int(options.get('period', 100))
    except (ValueError, TypeError):
        period = 100

    hh = df['high'].rolling(window=period).max()
    ll = df['low'].rolling(window=period).min()
    diff = hh - ll

    # Standard Retracements + Extensions
    return pd.DataFrame({
        # --- Standard Retracements ---
        'fib_0': hh,
        'fib_236': hh - (0.236 * diff),
        'fib_382': hh - (0.382 * diff),
        'fib_50': hh - (0.5 * diff),
        'fib_618': hh - (0.618 * diff),
        'fib_786': hh - (0.786 * diff),
        'fib_100': ll,
        
        # --- Fibonacci Extensions (Price Targets) ---
        # Upward projections (Targets for Longs)
        'ext_1272': hh + (0.272 * diff),
        'ext_1618': hh + (0.618 * diff),
        'ext_2618': hh + (1.618 * diff),
        
        # Downward projections (Targets for Shorts)
        'ext_neg_1272': ll - (0.272 * diff),
        'ext_neg_1618': ll - (0.618 * diff)
    }, index=df.index).dropna()