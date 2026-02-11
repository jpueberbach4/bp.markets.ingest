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
        "talib-validated": 1, 
        "polars": 1
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


def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> pl.Expr:
    """
    High-performance Polars-native ADX implementation.
    Returns a struct containing adx, plus_di, and minus_di.
    """
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14

    span = 2 * period - 1
    epsilon = 1e-12

    prev_close = pl.col("close").shift(1)
    prev_high = pl.col("high").shift(1)
    prev_low = pl.col("low").shift(1)

    tr = pl.max_horizontal([
        pl.col("high") - pl.col("low"),
        (pl.col("high") - prev_close).abs(),
        (pl.col("low") - prev_close).abs()
    ])

    up_move = pl.col("high") - prev_high
    down_move = prev_low - pl.col("low")

    plus_dm = pl.when((up_move > down_move) & (up_move > 0)).then(up_move).otherwise(0.0)
    minus_dm = pl.when((down_move > up_move) & (down_move > 0)).then(down_move).otherwise(0.0)

    atr_smooth = tr.ewm_mean(span=span, adjust=False)
    plus_di_smooth = plus_dm.ewm_mean(span=span, adjust=False)
    minus_di_smooth = minus_dm.ewm_mean(span=span, adjust=False)

    plus_di = 100 * (plus_di_smooth / (atr_smooth + epsilon))
    minus_di = 100 * (minus_di_smooth / (atr_smooth + epsilon))

    di_sum = plus_di + minus_di
    dx = 100 * (plus_di - minus_di).abs() / pl.when(di_sum == 0).then(1.0).otherwise(di_sum)
    adx = dx.ewm_mean(span=span, adjust=False)

    return pl.struct([
        adx.alias("adx"),
        plus_di.alias("plus_di"),
        minus_di.alias("minus_di")
    ]).alias(indicator_str)
