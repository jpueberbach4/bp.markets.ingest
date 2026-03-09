import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "Pivot Points are significant technical levels used to determine the overall "
        "trend of the market over different time frames. Based on the 'Floor Pivot' "
        "method, this indicator calculates a central Pivot Point (PP) using the average "
        "of the previous period's high, low, and close. It then derives multiple "
        "levels of support (S1, S2) and resistance (R1, R2) to identify potential "
        "turning points or breakout targets in price action."
    )

def meta() -> Dict:
    """
    Metadata for the dual-engine orchestrator.
    """
    return {
        "author": "Google Gemini",
        "version": 1.2,
        "verified": 1,
        "polars": 1,
        "needs": "surface-colouring"
    }

def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for Pivot Points.
    """
    try:
        lookback = int(options.get('lookback', 1))
    except (ValueError, TypeError):
        lookback = 1
    return lookback * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    """
    return {
        "lookback": args[0] if len(args) > 0 else "1"
    }

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    """
    Fixed Polars Variant for Pivot Points.
    """
    try:
        period = int(options.get('lookback', 1))
    except (ValueError, TypeError):
        period = 1

    high = pl.col("high").cast(pl.Float64)
    low = pl.col("low").cast(pl.Float64)
    close = pl.col("close").cast(pl.Float64)

    if period == 1:
        prev_h = high.shift(1)
        prev_l = low.shift(1)
    else:
        prev_h = high.shift(1).rolling_max(window_size=period, min_samples=1)
        prev_l = low.shift(1).rolling_min(window_size=period, min_samples=1)
    
    prev_c = close.shift(1)

    pp = (prev_h + prev_l + prev_c) / 3.0
    
    diff = prev_h - prev_l
    r1 = (2.0 * pp) - prev_l
    s1 = (2.0 * pp) - prev_h
    r2 = pp + diff
    s2 = pp - diff

    return [
        pp.alias(f"{indicator_str}__pp"),
        r1.alias(f"{indicator_str}__r1"),
        s1.alias(f"{indicator_str}__s1"),
        r2.alias(f"{indicator_str}__r2"),
        s2.alias(f"{indicator_str}__s2")
    ]
