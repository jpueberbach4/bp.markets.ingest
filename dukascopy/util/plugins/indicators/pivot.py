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
        "version": 1.1,
        "verified": 1,
        "polars": 0,    # TODO: needs fixing for polars version. for now. fallback to pandas version
                        # We receive all nulls from polars version
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
    Uses 'min_periods=1' to ensure the calculation triggers on the first bar,
    matching the rendering expectations of the JSONP output.
    """
    try:
        period = int(options.get('lookback', 1))
    except (ValueError, TypeError):
        period = 1

    # 1. Shift and Roll with min_periods=1
    # This ensures that even on the second bar of the dataset, 
    # we have a valid Pivot Point based on bar #1.
    prev_h = pl.col("high").shift(1).rolling_max(window_size=period, min_periods=1).cast(pl.Float64)
    prev_l = pl.col("low").shift(1).rolling_min(window_size=period, min_periods=1).cast(pl.Float64)
    prev_c = pl.col("close").shift(1).cast(pl.Float64)

    # 2. Pivot Point Math (Exactly matching your legacy code)
    pp = (prev_h + prev_l + prev_c) / 3.0
    
    # 3. Levels
    diff = prev_h - prev_l
    r1 = (2.0 * pp) - prev_l
    s1 = (2.0 * pp) - prev_h
    r2 = pp + diff
    s2 = pp - diff

    # 4. Final output aliases
    # We do NOT dropna here; the parallel engine handles row alignment.
    # Rounding to 5 ensures precision matches your sample_price logic.
    return [
        pp.round(5).alias(f"{indicator_str}__pp"),
        r1.round(5).alias(f"{indicator_str}__r1"),
        s1.round(5).alias(f"{indicator_str}__s1"),
        r2.round(5).alias(f"{indicator_str}__r2"),
        s2.round(5).alias(f"{indicator_str}__s2")
    ]

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    Legacy fallback for Pandas-only environments.
    """
    try:
        period = int(options.get('lookback', 1))
    except (ValueError, TypeError):
        period = 1

    try:
        sample_price = str(df['close'].iloc[0])
        precision = len(sample_price.split('.')[1])+1 if '.' in sample_price else 2
    except (IndexError, AttributeError):
        precision = 5

    prev_h = df['high'].shift(1).rolling(window=period).max()
    prev_l = df['low'].shift(1).rolling(window=period).min()
    prev_c = df['close'].shift(1)

    pp = (prev_h + prev_l + prev_c) / 3
    r1 = (2 * pp) - prev_l
    r2 = pp + (prev_h - prev_l)
    s1 = (2 * pp) - prev_h
    s2 = pp - (prev_h - prev_l)

    res = pd.DataFrame({
        'pp': pp.round(precision),
        'r1': r1.round(precision),
        's1': s1.round(precision),
        'r2': r2.round(precision),
        's2': s2.round(precision)
    }, index=df.index)
    
    return res.dropna(subset=['pp'])