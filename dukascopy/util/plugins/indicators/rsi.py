import pandas as pd
import numpy as np
import polars as pl
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

def meta() -> Dict:
    """
    Any other metadata to pass via API
    """
    return {
        "author": "Google Gemini",
        "version": 1.1,
        "panel": 1,
        "verified": 1,
        "polars": 1  # Enabled for high-speed execution
    }

def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for RSI.
    """
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14

    return period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    """
    return {
        "period": args[0] if len(args) > 0 else "14"
    }

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> pl.Expr:
    """
    High-performance Polars-native calculation using Wilder's Smoothing.
    """
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14

    # 1. Calculate price differences
    diff = pl.col("close").diff()

    # 2. Separate gains and losses
    gain = pl.when(diff > 0).then(diff).otherwise(0)
    loss = pl.when(diff < 0).then(-diff).otherwise(0)

    # 3. Apply Wilder's Smoothing (EWM with alpha = 1/period)
    # In Polars ewm_mean: span = (2 / alpha) - 1. 
    # For Wilder's alpha (1/N), span = 2N - 1
    avg_gain = gain.ewm_mean(span=2 * period - 1, adjust=False)
    avg_loss = loss.ewm_mean(span=2 * period - 1, adjust=False)

    # 4. Calculate RSI
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi.alias(indicator_str)

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    Legacy Pandas fallback.
    """
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14

    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    return pd.DataFrame({ 'rsi': rsi }, index=df.index).dropna()