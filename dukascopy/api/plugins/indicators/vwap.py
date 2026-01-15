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

def meta()->Dict:
    """
    Any other metadata to pass via API
    """
    return {
        "author": "Google Gemini",
        "version": 1.0,
        "verified": 1
    }
    
def warmup_count(options: Dict[str, Any]) -> int:
    """
    VWAP is session-based. To be accurate, it must calculate from 
    the very first bar of the current trading session.
    A buffer of 500 bars is a safe default for intraday charts 
    to capture the session start.
    """
    # 500 bars covers a full standard equity session on 1m/2m timeframes.
    return 500

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    VWAP typically calculates on the full session.
    """
    return {}

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    High-performance vectorized Volume Weighted Average Price (VWAP).
    Formula: Cumulative(Typical Price * Volume) / Cumulative(Volume)
    """
    
    # 1. Determine Price Precision
    try:
        sample_val = df['close'].iloc[0]
        sample_price = f"{sample_val:.10f}".rstrip('0')
        precision = len(sample_price.split('.')[1]) if '.' in sample_price else 2
        precision = min(max(precision, 2), 8) 
    except (IndexError, AttributeError, ValueError):
        precision = 2

    # 2. Calculation Logic
    # Typical Price = (High + Low + Close) / 3
    tp = (df['high'] + df['low'] + df['close']) / 3
    pv = tp * df['volume']

    # 3. Session Reset Logic (Vectorized)
    # VWAP usually resets every day. We detect date changes in the index.
    if isinstance(df.index, pd.DatetimeIndex):
        day_changed = df.index.normalize() != df.index.to_series().shift(1).dt.normalize()
        group_id = day_changed.cumsum()
        
        # Cumulative sums per session
        cum_pv = pv.groupby(group_id).cumsum()
        cum_vol = df['volume'].groupby(group_id).cumsum()
    else:
        # Fallback to global cumulative sum if no datetime index
        cum_pv = pv.cumsum()
        cum_vol = df['volume'].cumsum()

    # Calculate VWAP
    vwap = cum_pv / cum_vol.replace(0, np.nan)

    # 4. Final Formatting and Rounding
    # Preserving the original index for O(1) merging in parallel.py
    res = pd.DataFrame({
        'vwap': vwap.round(precision)
    }, index=df.index)
    
    return res.fillna(method='ffill')