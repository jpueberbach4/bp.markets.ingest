import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "The Rate of Change (ROC) is a pure momentum oscillator that measures the "
        "percentage change in price between the current period and a specific "
        "number of periods ago. It fluctuates above and below a Zero Line; "
        "positive values indicate bullish momentum, while negative values indicate "
        "bearish momentum. It is widely used to identify trend strength, "
        "overbought/oversold conditions, and momentum divergences."
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
        "polars": 1  # Flag to trigger high-speed Polars execution
    }

def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for Rate of Change (ROC).
    Requires 'period' rows for historical comparison.
    """
    try:
        period = int(options.get('period', 9))
    except (ValueError, TypeError):
        period = 9
    return period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: roc_12 -> {'period': '12'}
    """
    return {
        "period": args[0] if len(args) > 0 else "9"
    }

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> pl.Expr:
    """
    High-performance Polars-native calculation for ROC.
    Uses Lazy expressions for O(1) memory mapping.
    """
    try:
        period = int(options.get('period', 12))
    except (ValueError, TypeError):
        period = 12

    # 1. Historical Price Lookup
    # We shift 'close' by the period to get the comparison base
    price_n = pl.col("close").shift(period)

    # 2. Percentage Change Calculation
    # Polars handles division by zero by producing 'null' or 'inf', 
    # which we fill for stability.
    roc = ((pl.col("close") - price_n) / price_n) * 100

    # 3. Final Alias and Rounding
    return roc.fill_nan(0).fill_null(0).round(3).alias(indicator_str)

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    Legacy fallback for Pandas-only environments.
    """
    try:
        period = int(options.get('period', 12))
    except (ValueError, TypeError):
        period = 12

    precision = 3 

    price_n = df['close'].shift(period)
    roc = ((df['close'] - price_n) / price_n.replace(0, np.nan)) * 100

    res = pd.DataFrame({
        'roc': roc.round(precision)
    }, index=df.index)
    
    return res.dropna(subset=['roc'])