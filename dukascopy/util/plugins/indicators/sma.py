import polars as pl
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "The Simple Moving Average (SMA) is one of the most fundamental technical "
        "indicators. It calculates the average price of an asset over a specific "
        "number of periods by adding up the closing prices and dividing by the "
        "total count. It is primarily used to smooth out price action, identify "
        "trend direction, and act as dynamic support or resistance levels."
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
    Calculates the required warmup rows for the SMA.
    """
    try:
        period = int(options.get('period', 9))
    except (ValueError, TypeError):
        period = 9
    return period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: sma_50 -> {'period': '50'}
    """
    return {
        "period": args[0] if len(args) > 0 else "9"
    }

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> pl.Expr:
    """
    High-performance Polars-native calculation using Lazy expressions.
    """
    # Parse Parameters
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14

    # This is an instruction, not a calculation yet.
    return pl.col("close").rolling_mean(window_size=period).alias(indicator_str)

def calculate(df: Any, options: Dict[str, Any]) -> Any:
    """
    Legacy fallback for Pandas-only environments.
    """
    # If the engine is still Pandas, we maintain the original logic
    import pandas as pd
    period = int(options.get('period', 14))
    sma = df['close'].rolling(window=period).mean()
    return pd.DataFrame({'sma': sma}, index=df.index).dropna()