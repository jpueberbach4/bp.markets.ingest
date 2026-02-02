import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "Chande Momentum Oscillator (CMO) is a technical momentum indicator that "
        "measures the difference between the sum of all recent gains and the sum "
        "of all recent losses, then divides the result by the sum of all price "
        "movement over the period. Unlike RSI, it uses unfiltered data in its "
        "numerator, making it more sensitive to extreme price movements."
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
    Calculates the required warmup rows for CMO.
    """
    try:
        period = int(options.get('period', 9))
    except (ValueError, TypeError):
        period = 9
    return period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    """
    return {
        "period": args[0] if len(args) > 0 else "9"
    }

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> pl.Expr:
    """
    High-performance Polars-native calculation for CMO.
    """
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14

    # 1. Calculate Price Change
    diff = pl.col("close").diff()

    # 2. Identify Gains and Losses
    gain = pl.when(diff > 0).then(diff).otherwise(0)
    loss = pl.when(diff < 0).then(diff.abs()).otherwise(0)

    # 3. Calculate Rolling Sums
    sum_g = gain.rolling_sum(window_size=period)
    sum_l = loss.rolling_sum(window_size=period)

    # 4. CMO Formula: 100 * (SumG - SumL) / (SumG + SumL)
    # fill_nan handles division by zero for stagnant price movement
    cmo = (100 * (sum_g - sum_l) / (sum_g + sum_l)).fill_nan(None)

    return cmo.alias(indicator_str)

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    Legacy Pandas fallback.
    """
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14

    delta = df['close'].diff()
    gains = delta.where(delta > 0, 0)
    losses = delta.where(delta < 0, 0).abs()
    
    sum_gains = gains.rolling(window=period).sum()
    sum_losses = losses.rolling(window=period).sum()
    
    total_movement = sum_gains + sum_losses
    cmo_values = 100 * ((sum_gains - sum_losses) / total_movement.replace(0, np.nan))
    
    return pd.DataFrame({'cmo': cmo_values}, index=df.index).dropna()