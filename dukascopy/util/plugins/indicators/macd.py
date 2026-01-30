import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "MACD is a trend-following momentum indicator that shows the relationship "
        "between two moving averages of an asset’s price. It consists of the MACD "
        "Line (the difference between a fast and slow EMA), a Signal Line (an EMA "
        "of the MACD Line), and a Histogram which represents the distance between "
        "the two."
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
        "polars": 1  # Enable high-speed Rust-backed execution
    }

def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for MACD convergence.
    """
    try:
        slow_period = int(options.get('slow', 26))
    except (ValueError, TypeError):
        slow_period = 26
    return slow_period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: macd_12_26_9 -> {'fast': '12', 'slow': '26', 'signal': '9'}
    """
    return {
        "fast": args[0] if len(args) > 0 else "12",
        "slow": args[1] if len(args) > 1 else "26",
        "signal": args[2] if len(args) > 2 else "9"
    }

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    """
    High-performance Polars-native MACD.
    Returns a list of 3 expressions (macd, signal, hist) that Polars will
    calculate in a single optimized pass.
    """
    try:
        fast = int(options.get('fast', 12))
        slow = int(options.get('slow', 26))
        signal = int(options.get('signal', 9))
    except (ValueError, TypeError):
        fast, slow, signal = 12, 26, 9

    # 1. Define the base EMAs
    ema_fast = pl.col("close").ewm_mean(span=fast, adjust=False)
    ema_slow = pl.col("close").ewm_mean(span=slow, adjust=False)

    # 2. Derive the MACD Line
    macd_line = (ema_fast - ema_slow)
    
    # 3. Derive the Signal Line (EMA of the MACD line)
    signal_line = macd_line.ewm_mean(span=signal, adjust=False)
    
    # 4. Derive the Histogram
    hist = macd_line - signal_line

    # Return as a list of aliased expressions
    # Using the __ prefix for the nested dictionary logic in parallel.py
    return [
        macd_line.alias(f"{indicator_str}__macd"),
        signal_line.alias(f"{indicator_str}__signal"),
        hist.alias(f"{indicator_str}__hist")
    ]

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    Legacy Pandas fallback.
    """
    try:
        fast = int(options.get('fast', 12))
        slow = int(options.get('slow', 26))
        signal = int(options.get('signal', 9))
    except (ValueError, TypeError):
        fast, slow, signal = 12, 26, 9

    ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
    
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line

    return pd.DataFrame({
        'macd': macd_line,
        'signal': signal_line,
        'hist': hist
    }, index=df.index).dropna()