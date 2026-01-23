import pandas as pd
import numpy as np
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "The Elder Ray Index (also known as Bull and Bear Power) measures the amount "
        "of buying and selling pressure in the market. It uses an Exponential Moving "
        "Average (EMA) as a baseline for value. Bull Power is calculated by subtracting "
        "the EMA from the high of each bar, while Bear Power is calculated by "
        "subtracting the EMA from the low of each bar."
    )

def meta()->Dict:
    """
    Any other metadata to pass via API
    """
    return {
        "author": "Google Gemini",
        "version": 1.0,
        "panel": 1,
        "verified": 1
    }

def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for the Elder Ray Index.
    Elder Ray uses an EMA (Exponential Moving Average) for its baseline.
    We use 3x the period to ensure the EMA has converged.
    """
    try:
        period = int(options.get('period', 13))
    except (ValueError, TypeError):
        period = 13

    # Consistent with EMA-based indicators (3x period)
    return period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: elderray_13 -> {'period': '13'}
    """
    return {
        "period": args[0] if len(args) > 0 else "13"
    }

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    High-performance vectorized Elder Ray Index calculation.
    Formula: 
    - Bull Power = High - EMA(period)
    - Bear Power = Low - EMA(period)
    """
    # 1. Parse Parameters
    try:
        period = int(options.get('period', 13))
    except (ValueError, TypeError):
        period = 13

    # 2. Determine Price Precision for rounding
    try:
        sample_price = str(df['close'].iloc[0])
        precision = len(sample_price.split('.')[1])+1 if '.' in sample_price else 2
    except (IndexError, AttributeError):
        precision = 5

    # 3. Calculation Logic
    # Calculate EMA using the ewm function (adjust=False matches the standard formula)
    ema = df['close'].ewm(span=period, adjust=False).mean()
    
    # Calculate Power components (Vectorized)
    bull_power = df['high'] - ema
    bear_power = df['low'] - ema

    # 4. Final Formatting and Rounding
    # Preserving the original index for O(1) merging in parallel.py
    res = pd.DataFrame({
        'bull_power': bull_power.round(precision),
        'bear_power': bear_power.round(precision)
    }, index=df.index)
    
    # Drop rows where the EMA hasn't stabilized (warm-up period)
    return res.dropna()