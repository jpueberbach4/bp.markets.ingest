import pandas as pd
import numpy as np
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "The Relative Strength Index (RSI) is a popular momentum oscillator that "
        "measures the speed and change of price movements. It oscillates between "
        "zero and 100, traditionally using a 14-period lookback. RSI is primarily "
        "used to identify overbought conditions (above 70) and oversold conditions "
        "(below 30), as well as spotting trend reversals and price-momentum "
        "divergences."
    )

def meta()->Dict:
    """
    Any other metadata to pass via API
    """
    return {
        "author": "Google Gemini",
        "version": 1.0
    }

def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for RSI.
    RSI uses Wilder's Smoothing (recursive), requiring a buffer
    to ensure the oscillator values have stabilized.
    """
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14

    # 3x period is the standard for Wilder's/EMA convergence
    return period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: rsi_14 -> {'period': '14'}
    """
    return {
        "period": args[0] if len(args) > 0 else "14"
    }

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    High-performance vectorized Relative Strength Index (RSI) calculation.
    Uses Wilder's Smoothing (alpha = 1/period).
    """
    # 1. Parse Parameters
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14

    # 2. Determine Precision
    # RSI is typically an oscillator rounded to 2 decimals
    precision = 2 

    # 3. Calculation Logic
    # Calculate price changes
    delta = df['close'].diff()

    # Separate gains and losses (Vectorized)
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    # Wilder's Smoothing (EMA with alpha = 1/period)
    # In Pandas EWM, com = (1/alpha) - 1. For Wilder's: com = period - 1
    avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=False).mean()

    # Calculate RS and RSI
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    
    # Handle the case where avg_loss is 0 (RSI would be 100)
    rsi = rsi.fillna(100)

    # 4. Final Formatting and Rounding
    # Preserving the original index for O(1) merging in parallel.py
    res = pd.DataFrame({
        'rsi': rsi.round(precision)
    }, index=df.index)
    
    # Drop the first row (NaN from .diff()) and return
    return res.dropna(subset=['rsi'])