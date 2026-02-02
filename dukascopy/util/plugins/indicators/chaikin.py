import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "The Chaikin Oscillator measures the momentum of the Accumulation Distribution Line (ADL) "
        "using the MACD formula. It calculates the difference between a short-term (default 3) "
        "and a long-term (default 10) Exponential Moving Average of the ADL."
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
    Calculates the required warmup rows for the Chaikin Oscillator.
    Standard requirement is 3x the long EMA period.
    """
    try:
        long_period = int(options.get('long', 10))
    except (ValueError, TypeError):
        long_period = 10
    return long_period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: chaikin_3_10 -> {'short': '3', 'long': '10'}
    """
    return {
        "short": args[0] if len(args) > 0 else "3",
        "long": args[1] if len(args) > 1 else "10"
    }

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> pl.Expr:
    """
    High-performance Polars-native Chaikin Oscillator.
    Bypasses the GIL by chaining ADL and EMA calculations in Rust.
    """
    try:
        short_period = int(options.get('short', 3))
        long_period = int(options.get('long', 10))
    except (ValueError, TypeError):
        short_period, long_period = 3, 10

    # 1. Calculate Money Flow Multiplier and Volume
    h_l_range = pl.col("high") - pl.col("low")
    mfm = ((pl.col("close") - pl.col("low")) - (pl.col("high") - pl.col("close"))) / h_l_range
    
    # 2. Derive ADL (Cumulative Sum of Money Flow Volume)
    # fill_nan handles flat bars where High == Low
    adl = (mfm.fill_nan(0) * pl.col("volume")).cum_sum()
    
    # 3. Chaikin Formula: EMA(ADL, short) - EMA(ADL, long)
    # Polars optimizes this so the ADL isn't recalculated for each EMA
    chaikin = adl.ewm_mean(span=short_period, adjust=False) - adl.ewm_mean(span=long_period, adjust=False)

    return chaikin.alias(indicator_str)

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    Legacy Pandas fallback.
    """
    try:
        short_period = int(options.get('short', 3))
        long_period = int(options.get('long', 10))
    except (ValueError, TypeError):
        short_period, long_period = 3, 10

    h_l_range = (df['high'] - df['low']).replace(0, np.nan)
    mfm = ((df['close'] - df['low']) - (df['high'] - df['close'])) / h_l_range
    mfm = mfm.fillna(0)
    
    mfv = mfm * df['volume']
    adl = mfv.cumsum()
    
    ema_short = adl.ewm(span=short_period, adjust=False).mean()
    ema_long = adl.ewm(span=long_period, adjust=False).mean()
    
    return pd.DataFrame({'chaikin': ema_short - ema_long}, index=df.index)