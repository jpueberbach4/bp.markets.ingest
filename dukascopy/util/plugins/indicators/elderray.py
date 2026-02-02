import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "The Elder Ray Index (Bull and Bear Power) measures buying and selling "
        "pressure. Bull Power is High minus EMA, and Bear Power is Low minus EMA. "
        "It uses an EMA as a baseline for value."
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
    Calculates the required warmup rows for the Elder Ray Index.
    """
    try:
        period = int(options.get('period', 13))
    except (ValueError, TypeError):
        period = 13
    return period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: elderray_13 -> {'period': '13'}
    """
    return {
        "period": args[0] if len(args) > 0 else "13"
    }

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    """
    High-performance Polars-native calculation for Elder Ray Index.
    """
    try:
        period = int(options.get('period', 13))
    except (ValueError, TypeError):
        period = 13

    # 1. Calculate the baseline EMA
    # Polars ewm_mean is GIL-free and optimized in Rust
    ema = pl.col("close").ewm_mean(span=period, adjust=False)

    # 2. Calculate Power components
    bull_power = pl.col("high") - ema
    bear_power = pl.col("low") - ema

    # 3. Return aliased expressions for the nested orchestrator
    # Using __ prefix to trigger dictionary grouping in parallel.py
    return [
        bull_power.alias(f"{indicator_str}__bull_power"),
        bear_power.alias(f"{indicator_str}__bear_power")
    ]

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    Legacy Pandas fallback.
    """
    try:
        period = int(options.get('period', 13))
    except (ValueError, TypeError):
        period = 13

    ema = df['close'].ewm(span=period, adjust=False).mean()
    bull_power = df['high'] - ema
    bear_power = df['low'] - ema

    return pd.DataFrame({
        'bull_power': bull_power,
        'bear_power': bear_power
    }, index=df.index).dropna()