import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "Average Directional Index (ADX) quantifies trend strength without regard "
        "to trend direction. It includes the +DI and -DI lines to indicate direction."
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
        "polars": 1  # Trigger high-speed Polars execution path
    }

def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for ADX.
    Wilder's smoothing (EWM) typically requires 3x the period to converge.
    """
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14
    return period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    """
    return {
        "period": args[0] if len(args) > 0 else "14"
    }

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    """
    High-performance Polars-native ADX calculation.
    """
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14

    # 1. Shifts for High, Low, Close
    p_high = pl.col("high").shift(1)
    p_low = pl.col("low").shift(1)
    p_close = pl.col("close").shift(1)

    # 2. Calculate True Range (TR)
    tr = pl.max_horizontal([
        pl.col("high") - pl.col("low"),
        (pl.col("high") - p_close).abs(),
        (pl.col("low") - p_close).abs()
    ])

    # 3. Calculate Directional Movement (DM)
    diff_high = pl.col("high") - p_high
    diff_low = p_low - pl.col("low")

    plus_dm = pl.when((diff_high > diff_low) & (diff_high > 0)).then(diff_high).otherwise(0)
    minus_dm = pl.when((diff_low > diff_high) & (diff_low > 0)).then(diff_low).otherwise(0)

    # 4. Wilder's Smoothing (alpha = 1/N -> span = 2N - 1)
    # Smooth TR, +DM, and -DM
    atr_s = tr.ewm_mean(span=2 * period - 1, adjust=False)
    plus_s = plus_dm.ewm_mean(span=2 * period - 1, adjust=False)
    minus_s = minus_dm.ewm_mean(span=2 * period - 1, adjust=False)

    # 5. Calculate +DI and -DI
    plus_di = (100 * plus_s / atr_s)
    minus_di = (100 * minus_s / atr_s)

    # 6. Calculate DX and ADX
    # Note: Using fill_nan(0) to handle potential division by zero
    dx = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di)).fill_nan(0)
    adx = dx.ewm_mean(span=2 * period - 1, adjust=False)

    # 7. Return aliased expressions for the nested orchestrator
    return [
        adx.alias(f"{indicator_str}__adx"),
        plus_di.alias(f"{indicator_str}__plus_di"),
        minus_di.alias(f"{indicator_str}__minus_di")
    ]

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    Legacy Pandas fallback.
    """
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14

    prev_close = df['close'].shift(1)
    prev_high = df['high'].shift(1)
    prev_low = df['low'].shift(1)
    
    tr = pd.concat([
        df['high'] - df['low'],
        (df['high'] - prev_close).abs(),
        (df['low'] - prev_close).abs()
    ], axis=1).max(axis=1)
    
    plus_dm = np.where((df['high'] - prev_high) > (prev_low - df['low']), 
                        np.maximum(df['high'] - prev_high, 0), 0)
    minus_dm = np.where((prev_low - df['low']) > (df['high'] - prev_high), 
                         np.maximum(prev_low - df['low'], 0), 0)
    
    atr_smooth = tr.ewm(alpha=1/period, adjust=False).mean()
    plus_di_smooth = pd.Series(plus_dm, index=df.index).ewm(alpha=1/period, adjust=False).mean()
    minus_di_smooth = pd.Series(minus_dm, index=df.index).ewm(alpha=1/period, adjust=False).mean()
    
    plus_di = 100 * (plus_di_smooth / atr_smooth)
    minus_di = 100 * (minus_di_smooth / atr_smooth)
    
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.ewm(alpha=1/period, adjust=False).mean()
    
    return pd.DataFrame({
        'adx': adx,
        'plus_di': plus_di,
        'minus_di': minus_di
    }, index=df.index).dropna()