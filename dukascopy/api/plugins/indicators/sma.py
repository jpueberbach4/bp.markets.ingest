import pandas as pd
import numpy as np
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "The Simple Moving Average (SMA) is one of the most fundamental technical "
        "indicators. It calculates the average price of an asset over a specific "
        "number of periods by adding up the closing prices and dividing by the "
        "total count. It is primarily used to smooth out price action, identify "
        "trend direction, and act as dynamic support or resistance levels."
    )

def meta()->Dict:
    """
    Any other metadata to pass via API
    """
    return {
        "author": "Google Gemini",
        "version": 1.0,
        "verified": 1
    }

def warmup_count(options: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculates the required warmup time in seconds based on the SMA period
    and a wide range of timeframe strings (1m to 1Y).
    """
    # 1. Parse the period from options
    try:
        period = int(options.get('period', 9))
    except (ValueError, TypeError):
        period = 9

    return period*3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: sma_50 -> {'period': '50'}
    """
    return {
        "period": args[0] if len(args) > 0 else "9"
    }

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    High-performance vectorized Simple Moving Average (SMA).
    """
    # 1. Parse Parameters
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14

    # 2. Determine Price Precision for rounding
    try:
        sample_price = str(df['close'].iloc[0])
        precision = len(sample_price.split('.')[1]) if '.' in sample_price else 2
    except (IndexError, AttributeError):
        precision = 5

    # 3. Vectorized Calculation Logic
    # Calculates the rolling mean across the entire segment at once
    sma = df['close'].rolling(window=period).mean()

    # 4. Final Formatting and Rounding
    # Preserving the original index for O(1) merging in parallel.py
    res = pd.DataFrame({
        'sma': sma.round(precision)
    }, index=df.index)
    
    # Drop the warm-up period rows where the SMA hasn't stabilized
    return res.dropna(subset=['sma'])