import polars as pl
import pandas as pd
import numpy as np
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "The MidPoint Over Period (MIDPOINT) indicator evaluates the average price movement "
        "by calculating the midpoint between the highest and lowest values of a single "
        "price series (usually Close) over a specified period. It provides a smoother "
        "representation of price action than raw prices."
    )

def meta() -> Dict:
    """
    Metadata for the dual-engine orchestrator.
    """
    return {
        "author": "Google Gemini",
        "version": 1.0,
        "panel": 1,
        "verified": 1,
        "polars": 1
    }

def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows.
    """
    return int(options.get('period', 14))

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    """
    return {"period": args[0] if len(args) > 0 else "14"}

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> pl.Expr:
    """
    High-performance Polars-native calculation for MidPoint.
    Matches TA-Lib 'MIDPOINT' logic.
    """
    try:
        p = int(options.get('period', 14))
    except (ValueError, TypeError):
        p = 14

    series = pl.col("close")
    
    return ((series.rolling_max(window_size=p) + series.rolling_min(window_size=p)) / 2).alias(indicator_str)

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    Legacy fallback for Pandas-only environments.
    """
    try:
        p = int(options.get('period', 14))
    except (ValueError, TypeError):
        p = 14

    hh = df['close'].rolling(window=p).max()
    ll = df['close'].rolling(window=p).min()
    midpoint = (hh + ll) / 2
    
    return pd.DataFrame({'midpoint': midpoint}, index=df.index).dropna()