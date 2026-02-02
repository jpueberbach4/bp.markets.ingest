import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "Keltner Channels are a volatility-based envelope indicator. They consist of "
        "three lines: a Middle Line (typically an Exponential Moving Average), and "
        "Upper and Lower Channels calculated using the Average True Range (ATR). "
        "Unlike Bollinger Bands which use standard deviation, Keltner Channels use "
        "ATR to create a smoother, more consistent envelope that helps identify "
        "trend direction and price breakouts."
    )

def meta() -> Dict:
    """
    Metadata for the dual-engine orchestrator.
    """
    return {
        "author": "Google Gemini",
        "version": 1.1,
        "verified": 1,
        "polars": 1,  # Flag to trigger high-speed Polars execution
        "needs": "surface-colouring"
    }

def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for Keltner Channels.
    """
    try:
        ema_period = int(options.get('period', 20))
        atr_period = int(options.get('atr_period', 10))
    except (ValueError, TypeError):
        ema_period, atr_period = 20, 10

    max_period = max(ema_period, atr_period)
    return max_period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: keltner_20_10_2 -> {'period': '20', 'atr_period': '10', 'multiplier': '2'}
    """
    return {
        "period": args[0] if len(args) > 0 else "20",
        "atr_period": args[1] if len(args) > 1 else "10",
        "multiplier": args[2] if len(args) > 2 else "1.0"
    }

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    """
    High-performance Polars-native calculation for Keltner Channels.
    """
    try:
        ema_period = int(options.get('period', 20))
        atr_period = int(options.get('atr_period', 10))
        multiplier = float(options.get('multiplier', 1.0))
    except (ValueError, TypeError):
        ema_period, atr_period, multiplier = 20, 10, 1.0

    # 1. Mid Line (EMA)
    mid = pl.col("close").ewm_mean(span=ema_period, adjust=False)

    # 2. True Range Calculation
    prev_close = pl.col("close").shift(1)
    tr1 = pl.col("high") - pl.col("low")
    tr2 = (pl.col("high") - prev_close).abs()
    tr3 = (pl.col("low") - prev_close).abs()
    
    # max_horizontal for vectorized O(1) row-wise comparison
    true_range = pl.max_horizontal([tr1, tr2, tr3])

    # 3. ATR (Wilder's Smoothing)
    # alpha = 1 / period matches Wilder's original formula and your Pandas logic
    atr = true_range.ewm_mean(alpha=1/atr_period, adjust=False)

    # 4. Bands
    upper = mid + (multiplier * atr)
    lower = mid - (multiplier * atr)

    return [
        upper.round(5).alias(f"{indicator_str}__upper"),
        mid.round(5).alias(f"{indicator_str}__mid"),
        lower.round(5).alias(f"{indicator_str}__lower")
    ]

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    Legacy fallback for Pandas environments.
    """
    try:
        ema_period = int(options.get('period', 20))
        atr_period = int(options.get('atr_period', 10))
        multiplier = float(options.get('multiplier', 1.0))
    except (ValueError, TypeError):
        ema_period, atr_period, multiplier = 20, 10, 1.0

    try:
        sample_price = str(df['close'].iloc[0])
        precision = len(sample_price.split('.')[1])+1 if '.' in sample_price else 2
    except (IndexError, AttributeError):
        precision = 5

    mid = df['close'].ewm(span=ema_period, adjust=False).mean()

    prev_close = df['close'].shift(1)
    tr1 = df['high'] - df['low']
    tr2 = (df['high'] - prev_close).abs()
    tr3 = (df['low'] - prev_close).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = true_range.ewm(alpha=1/atr_period, min_periods=atr_period).mean()

    upper = mid + (multiplier * atr)
    lower = mid - (multiplier * atr)

    res = pd.DataFrame({
        'upper': upper.round(precision),
        'mid': mid.round(precision),
        'lower': lower.round(precision)
    }, index=df.index)
    
    warmup = max(ema_period, atr_period)
    return res.dropna(subset=['upper']).iloc[warmup:]