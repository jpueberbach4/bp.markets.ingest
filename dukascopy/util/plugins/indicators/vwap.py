import polars as pl
import pandas as pd
import numpy as np
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "VWAP (Volume Weighted Average Price) is a technical analysis indicator "
        "used to measure the average price an asset has traded at throughout the "
        "day, based on both volume and price. It provides traders with insight "
        "into both the trend and value of an asset. VWAP is often used as a "
        "benchmark by institutional traders to ensure they are executing orders "
        "close to the market average, rather than pushing the price away from "
        "its established value."
    )

def meta() -> Dict:
    """
    Metadata for the dual-engine orchestrator.
    """
    return {
        "author": "Google Gemini",
        "version": 1.1,
        "verified": 1,
        "polars": 1  # Flag to trigger high-speed Polars execution
    }

def warmup_count(options: Dict[str, Any]) -> int:
    """
    VWAP requires a calculation from the session start. 
    500 bars is a safe default for intraday high-frequency data.
    """
    return 500

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    VWAP typically takes no additional positional parameters.
    """
    return {}

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> pl.Expr:
    """
    High-performance Polars-native calculation for VWAP.
    Includes session-reset logic based on date changes.
    """
    # 1. Typical Price * Volume
    tp = (pl.col("high") + pl.col("low") + pl.col("close")) / 3
    pv = tp * pl.col("volume")

    # 2. Session Reset Logic
    # We use 'over' with a date-truncated window to reset cumulative sums every day
    # This assumes 'time' column is present as per project standards
    session_key = pl.col("time").dt.date()

    cum_pv = pv.cum_sum().over(session_key)
    cum_vol = pl.col("volume").cum_sum().over(session_key)

    # 3. Calculate and Round
    vwap = (cum_pv / cum_vol)

    return vwap.round(5).alias(indicator_str)

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    Legacy fallback for Pandas-only environments.
    """
    try:
        sample_val = df['close'].iloc[0]
        sample_price = f"{sample_val:.10f}".rstrip('0')
        precision = len(sample_price.split('.')[1])+1 if '.' in sample_price else 2
        precision = min(max(precision, 2), 8) 
    except (IndexError, AttributeError, ValueError):
        precision = 2

    tp = (df['high'] + df['low'] + df['close']) / 3
    pv = tp * df['volume']

    if isinstance(df.index, pd.DatetimeIndex):
        day_changed = df.index.normalize() != df.index.to_series().shift(1).dt.normalize()
        group_id = day_changed.cumsum()
        cum_pv = pv.groupby(group_id).cumsum()
        cum_vol = df['volume'].groupby(group_id).cumsum()
    else:
        cum_pv = pv.cumsum()
        cum_vol = df['volume'].cumsum()

    vwap = cum_pv / cum_vol.replace(0, np.nan)

    res = pd.DataFrame({
        'vwap': vwap.round(precision)
    }, index=df.index)
    
    return res.fillna(method='ffill')