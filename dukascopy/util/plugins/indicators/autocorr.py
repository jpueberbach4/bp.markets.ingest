import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "Autocorrelation measures the correlation of a signal with a delayed "
        "copy of itself. It is a powerful tool for identifying repeating patterns, "
        "momentum, or mean-reverting tendencies in price action."
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
        "polars": 1
    }

def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates required warmup rows.
    Autocorrelation requires the period plus the lag to begin calculation.
    """
    try:
        p = int(options.get('period', 30))
        lag = int(options.get('lag', 1))
    except (ValueError, TypeError):
        p, lag = 30, 1
    return p + lag

def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "period": args[0] if len(args) > 0 else "30",
        "lag": args[1] if len(args) > 1 else "1"
    }

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> pl.Expr:
    """
    High-performance Polars-native calculation for Autocorrelation.
    """
    try:
        p = int(options.get('period', 30))
        lag = int(options.get('lag', 1))
    except (ValueError, TypeError):
        p, lag = 30, 1

    return pl.rolling_corr(
        pl.col("close"), 
        pl.col("close").shift(lag), 
        window_size=p
    ).alias(indicator_str)

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    Legacy Pandas fallback.
    """
    p = int(options.get('period', 30))
    lag = int(options.get('lag', 1))
    
    auto_corr = df['close'].rolling(window=p).apply(lambda x: x.autocorr(lag=lag), raw=False)
    
    return pd.DataFrame({'value': auto_corr}, index=df.index)