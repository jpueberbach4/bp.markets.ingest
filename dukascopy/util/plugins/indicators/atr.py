import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "Average True Range (ATR) is a technical indicator that measures market "
        "volatility by decomposing the entire range of an asset price for a given "
        "period. Unlike directional indicators, ATR solely quantifies the degree "
        "of price fluctuation, including gaps from previous sessions."
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
    Calculates the required warmup rows for ATR.
    Wilder's smoothing (EWM) typically requires 3x the period to converge.
    """
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14
    return period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: atr_14 -> {'period': '14'}
    """
    return {
        "period": args[0] if len(args) > 0 else "14"
    }

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> pl.Expr:
    """
    High-performance Polars-native ATR calculation.
    """
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14

    # 1. Get Previous Close
    prev_close = pl.col("close").shift(1)

    # 2. Calculate the 3 components of True Range
    tr1 = pl.col("high") - pl.col("low")
    tr2 = (pl.col("high") - prev_close).abs()
    tr3 = (pl.col("low") - prev_close).abs()

    # 3. Calculate True Range (TR) using high-speed horizontal max
    # This avoids the 'concat' overhead found in Pandas
    tr = pl.max_horizontal([tr1, tr2, tr3])

    # 4. Apply Wilder's Smoothing
    # Alpha = 1/N for Wilder's. In Polars ewm_mean, span = 2N - 1
    return tr.ewm_mean(span=2 * period - 1, adjust=False).alias(indicator_str)

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    Legacy Pandas fallback.
    """
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14

    prev_close = df['close'].shift(1)
    tr1 = df['high'] - df['low']
    tr2 = (df['high'] - prev_close).abs()
    tr3 = (df['low'] - prev_close).abs()
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(com=period - 1, min_periods=period).mean()
    
    return pd.DataFrame({'atr': atr}, index=df.index).dropna()