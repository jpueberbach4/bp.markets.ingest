import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "ZigZag identifies significant turning points (peaks and troughs) "
        "that deviate from the previous swing by a specified percentage. "
        "It filters out noise to visualize the underlying trend structure."
        "Use 0.5 for forex and >1.0 for stocks."
    )

def meta() -> Dict:
    """
    Metadata for the dual-engine orchestrator.
    """
    return {
        "author": "Google Gemini",
        "version": 1.1,
        "panel": 0,           # 0 = Overlay on price chart
        "verified": 1,
        "talib-validated": 0, # TA-Lib doesn't have a standard ZigZag
        "polars": 0,          # Uses numpy loop internally
        "polars_input": 1     # Accepts Polars DataFrame directly
    }

def warmup_count(options: Dict[str, Any]) -> int:
    """
    ZigZag needs enough history to find at least one valid swing.
    """
    return 100

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    """
    return {
        "deviation": args[0] if len(args) > 0 else "0.5"
    }

def calculate(df: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    """
    High-performance ZigZag implementation for polars_input: 1.
    Uses a raw Numpy state machine to identify pivots, then Polars to interpolate lines.
    """
    try:
        deviation = float(options.get('deviation', 0.5))
    except (ValueError, TypeError):
        deviation = 5.0

    dev_threshold = deviation / 100.0

    highs = df['high'].to_numpy()
    lows = df['low'].to_numpy()
    n = len(highs)
    
    pivots = np.full(n, np.nan)
    
    if n < 2:
        return df.select(pl.lit(None).alias("zigzag"))

    trend = 0 
    last_pivot_idx = 0
    last_pivot_val = 0.0
    
    curr_ext_val = 0.0
    curr_ext_idx = 0

    start_price = highs[0]
    for i in range(1, n):
        if highs[i] > start_price * (1 + dev_threshold):
            trend = 1
            last_pivot_idx = 0
            last_pivot_val = lows[0] # Assume start was low
            curr_ext_val = highs[i]
            curr_ext_idx = i
            pivots[0] = last_pivot_val # Anchor start
            break
        elif lows[i] < start_price * (1 - dev_threshold):
            trend = -1
            last_pivot_idx = 0
            last_pivot_val = highs[0] # Assume start was high
            curr_ext_val = lows[i]
            curr_ext_idx = i
            pivots[0] = last_pivot_val # Anchor start
            break
            
    if trend == 0:
        return df.select(pl.lit(None).cast(pl.Float64).alias("zigzag"))

    for i in range(curr_ext_idx + 1, n):
        if trend == 1: # Uptrend, looking for higher High
            if highs[i] > curr_ext_val:
                curr_ext_val = highs[i]
                curr_ext_idx = i
            elif lows[i] < curr_ext_val * (1 - dev_threshold):
                pivots[curr_ext_idx] = curr_ext_val
                
                trend = -1
                last_pivot_idx = curr_ext_idx
                last_pivot_val = curr_ext_val
                
                curr_ext_val = lows[i]
                curr_ext_idx = i
                
        else: # Downtrend, looking for lower Low
            if lows[i] < curr_ext_val:
                curr_ext_val = lows[i]
                curr_ext_idx = i
            elif highs[i] > curr_ext_val * (1 + dev_threshold):
                pivots[curr_ext_idx] = curr_ext_val
                
                trend = 1
                last_pivot_idx = curr_ext_idx
                last_pivot_val = curr_ext_val
                
                curr_ext_val = highs[i]
                curr_ext_idx = i

    pivots[curr_ext_idx] = curr_ext_val
    
    zigzag_sparse = pl.Series("zigzag", pivots)
    
    return df.select(
        zigzag_sparse.interpolate().alias("zigzag")
    )