import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "Williams %R (Williams Percent Range) is a momentum indicator that measures "
        "overbought and oversold levels, similar to a Stochastic Oscillator. It "
        "compares the current closing price to the high-low range over a specific "
        "period (typically 14). The scale ranges from 0 to -100; readings from 0 "
        "to -20 are considered overbought, while readings from -80 to -100 are "
        "considered oversold. It is particularly effective at identifying "
        "potential reversals and trend strength."
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
    Calculates the required warmup rows for Williams %R.
    """
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14
    return period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: williamsr_14 -> {'period': '14'}
    """
    return {
        "period": args[0] if len(args) > 0 else "14"
    }

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> pl.Expr:
    """
    High-performance Polars-native calculation for Williams %R.
    """
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14

    # 1. Get rolling high and low over the lookback period
    hh = pl.col("high").rolling_max(window_size=period)
    ll = pl.col("low").rolling_min(window_size=period)
    
    # 2. Williams %R Formula: ((HH - Close) / (HH - LL)) * -100
    # Handle division by zero for flat price action by filling with a neutral -50
    range_diff = hh - ll
    williams_r = ((hh - pl.col("close")) / range_diff) * -100

    # 3. Final Alias and Rounding
    return williams_r.fill_nan(-50).fill_null(-50).round(2).alias(indicator_str)

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    High-performance vectorized Williams %R calculation (Pandas Fallback).
    """
    # 1. Parse Parameters
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14

    # 2. Determine Price Precision
    try:
        sample_val = df['close'].iloc[0]
        sample_price = f"{sample_val:.10f}".rstrip('0')
        precision = len(sample_price.split('.')[1])+1 if '.' in sample_price else 2
        precision = min(max(precision, 2), 8) 
    except (IndexError, AttributeError, ValueError):
        precision = 2

    # 3. Vectorized Calculation Logic
    hh = df['high'].rolling(window=period).max()
    ll = df['low'].rolling(window=period).min()
    range_diff = (hh - ll).replace(0, np.nan)
    williams_r = ((hh - df['close']) / range_diff) * -100

    # 4. Final Formatting and Rounding
    res = pd.DataFrame({
        'williams_r': williams_r.round(precision)
    }, index=df.index)
    
    return res.dropna(subset=['williams_r'])