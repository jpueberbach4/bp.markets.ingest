import polars as pl
import pandas as pd
import numpy as np
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "The Percentage Price Oscillator (PPO) measures the percentage difference "
        "between two moving averages. It is a scale-invariant momentum indicator, "
        "ideal for cross-asset comparisons where nominal price levels vary significantly."
    )

def meta() -> Dict:
    """
    Metadata for the dual-engine orchestrator.
    """
    return {
        "author": "Google Gemini",
        "version": 1.0, 
        "panel": 1,
        "verified": 1,
        "talib-validated": 1, 
        "polars": 1
    }

def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for PPO.
    Uses the slow EMA period as the base, multiplied for convergence.
    """
    try:
        slow = int(options.get('slow', 26))
    except (ValueError, TypeError):
        slow = 26
    return slow * 4

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: ppo_12_26_9
    """
    return {
        "fast": args[0] if len(args) > 0 else "12",
        "slow": args[1] if len(args) > 1 else "26",
        "signal": args[2] if len(args) > 2 else "9"
    }

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    """
    High-performance Polars-native calculation for PPO.
    Formula: ((FastEMA - SlowEMA) / SlowEMA) * 100
    """
    try:
        fast_p = int(options.get('fast', 12))
        slow_p = int(options.get('slow', 26))
        signal_p = int(options.get('signal', 9))
    except (ValueError, TypeError):
        fast_p, slow_p, signal_p = 12, 26, 9

    # 1. Calculate EMAs
    ema_fast = pl.col("close").ewm_mean(span=fast_p, adjust=False)
    ema_slow = pl.col("close").ewm_mean(span=slow_p, adjust=False)

    # 2. Calculate PPO Line
    ppo_line = ((ema_fast - ema_slow) / ema_slow) * 100

    # 3. Calculate Signal Line and Histogram
    signal_line = ppo_line.ewm_mean(span=signal_p, adjust=False)
    histogram = ppo_line - signal_line

    return [
        ppo_line.fill_nan(0).fill_null(0).alias(f"{indicator_str}__ppo"),
        signal_line.fill_nan(0).fill_null(0).alias(f"{indicator_str}__signal"),
        histogram.fill_nan(0).fill_null(0).alias(f"{indicator_str}__hist"),
    ]

