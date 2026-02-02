import polars as pl
import pandas as pd
import numpy as np
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "The Ultimate Oscillator (UO) is a momentum indicator designed to capture "
        "the 'buying pressure' across three different timeframes. By combining short, "
        "medium, and long-term price cycles into a single weighted value, it aims "
        "to avoid the pitfalls of indicators that are overly sensitive to short-term "
        "spikes. It oscillates between 0 and 100, with values above 70 indicating "
        "overbought conditions and values below 30 indicating oversold conditions."
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
    Calculates the required warmup rows for the Ultimate Oscillator.
    """
    try:
        p1 = int(options.get('p1', 7))
        p2 = int(options.get('p2', 14))
        p3 = int(options.get('p3', 28))
    except (ValueError, TypeError):
        p1, p2, p3 = 7, 14, 28

    max_period = max(p1, p2, p3)
    return max_period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: uo_7_14_28 -> {'p1': '7', 'p2': '14', 'p3': '28'}
    """
    return {
        "p1": args[0] if len(args) > 0 else "7",
        "p2": args[1] if len(args) > 1 else "14",
        "p3": args[2] if len(args) > 2 else "28"
    }

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> pl.Expr:
    """
    High-performance Polars-native calculation for Ultimate Oscillator.
    """
    try:
        p1 = int(options.get('p1', 7))
        p2 = int(options.get('p2', 14))
        p3 = int(options.get('p3', 28))
    except (ValueError, TypeError):
        p1, p2, p3 = 7, 14, 28

    # 1. Vectorized Pre-calculations (BP and TR)
    prev_close = pl.col("close").shift(1)
    
    # Buying Pressure: close - min(low, prev_close)
    min_low_pc = pl.min_horizontal([pl.col("low"), prev_close])
    bp = pl.col("close") - min_low_pc
    
    # True Range: max(high, prev_close) - min(low, prev_close)
    max_high_pc = pl.max_horizontal([pl.col("high"), prev_close])
    tr = max_high_pc - min_low_pc
    
    # 2. Vectorized Rolling Averages (BP_sum / TR_sum)
    # Division by zero/null is handled later by filling
    avg1 = bp.rolling_sum(window_size=p1) / tr.rolling_sum(window_size=p1)
    avg2 = bp.rolling_sum(window_size=p2) / tr.rolling_sum(window_size=p2)
    avg3 = bp.rolling_sum(window_size=p3) / tr.rolling_sum(window_size=p3)

    # 3. Ultimate Oscillator Formula
    uo = 100 * ((4 * avg1) + (2 * avg2) + avg3) / (4 + 2 + 1)

    # 4. Final Formatting
    return uo.fill_nan(50).fill_null(50).round(2).alias(indicator_str)

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    Legacy fallback for Pandas-only environments.
    """
    try:
        p1 = int(options.get('p1', 7))
        p2 = int(options.get('p2', 14))
        p3 = int(options.get('p3', 28))
    except (ValueError, TypeError):
        p1, p2, p3 = 7, 14, 28

    try:
        sample_val = df['close'].iloc[0]
        sample_price = f"{sample_val:.10f}".rstrip('0')
        precision = len(sample_price.split('.')[1])+1 if '.' in sample_price else 2
        precision = min(max(precision, 2), 8) 
    except (IndexError, AttributeError, ValueError):
        precision = 2

    prev_close = df['close'].shift(1)
    min_low_pc = np.minimum(df['low'].values, prev_close.values)
    bp = df['close'] - min_low_pc
    max_high_pc = np.maximum(df['high'].values, prev_close.values)
    tr = max_high_pc - min_low_pc
    tr_series = pd.Series(tr, index=df.index).replace(0, np.nan)

    def get_avg(period):
        return bp.rolling(window=period).sum() / tr_series.rolling(window=period).sum()

    avg1 = get_avg(p1)
    avg2 = get_avg(p2)
    avg3 = get_avg(p3)

    uo = 100 * ((4 * avg1) + (2 * avg2) + avg3) / (4 + 2 + 1)

    res = pd.DataFrame({
        'uo': uo.round(precision)
    }, index=df.index)
    
    return res.dropna(subset=['uo'])