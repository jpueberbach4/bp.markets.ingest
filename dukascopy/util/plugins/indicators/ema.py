import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "The Exponential Moving Average (EMA) is a type of moving average that "
        "places a greater weight and significance on the most recent data points. "
        "Unlike the Simple Moving Average, the EMA reacts more significantly to "
        "recent price changes, making it a favorite for identifying trend "
        "reversals and momentum in fast-moving markets."
    )

def meta() -> Dict:
    """
    Metadata for the dual-engine orchestrator.
    Note: polars is set to 1 as requested.
    """
    return {
        "author": "Google Gemini",
        "version": 1.1,
        "verified": 1,
        "polars": 1  
    }

def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for the EMA.
    We use 3x the period as the industry standard for convergence.
    """
    try:
        period = int(options.get('period', 9))
    except (ValueError, TypeError):
        period = 9

    return period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: ema_20 -> {'period': '20'}
    """
    return {
        "period": args[0] if len(args) > 0 else "9"
    }

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> pl.Expr:
    """
    High-performance Polars-native EMA calculation using Lazy expressions.
    """
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14

    # Using ewm_mean for recursive calculation (adjust=False matches standard TA)
    # This runs in Rust and bypasses the Python GIL.
    return pl.col("close").ewm_mean(span=period, adjust=False).alias(indicator_str)

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    Legacy Pandas fallback.
    """
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14

    # Vectorized EMA Calculation
    ema = df['close'].ewm(span=period, adjust=False).mean()

    # Preserving original index for merging
    res = pd.DataFrame({
        'ema': ema
    }, index=df.index)
    
    return res.dropna(subset=['ema']).iloc[period:]