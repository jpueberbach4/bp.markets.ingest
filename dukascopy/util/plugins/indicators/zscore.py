import polars as pl
import pandas as pd
import numpy as np
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "The Z-Score (Standard Score) is a statistical indicator that measures how "
        "many standard deviations a price is from its moving average. It helps "
        "traders identify extreme price movements and potential mean-reversion "
        "opportunities. A Z-Score of 0 means the price is exactly at the average, "
        "while scores above +2.0 or below -2.0 typically indicate overextended "
        "market conditions that may lead to a price correction."
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
    Calculates the required warmup rows for the Z-Score.
    Requires 'period' rows for rolling mean and standard deviation.
    """
    try:
        period = int(options.get('period', 20))
    except (ValueError, TypeError):
        period = 20
    return period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: zscore_20 -> {'period': '20'}
    """
    return {
        "period": args[0] if len(args) > 0 else "20"
    }

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    """
    High-performance Polars-native calculation for Z-Score.
    """
    try:
        period = int(options.get('period', 20))
    except (ValueError, TypeError):
        period = 20

    # 1. Rolling Stats
    mean = pl.col("close").rolling_mean(window_size=period)
    std_dev = pl.col("close").rolling_std(window_size=period)

    # 2. Z-Score Formula: (Price - Mean) / StdDev
    # Polars handles division by zero by producing null/nan, filled for stability
    z_score = (pl.col("close") - mean) / std_dev
    
    # 3. Directional Slope (1 for up, -1 for down)
    direction = (
        pl.when(z_score > z_score.shift(1))
        .then(pl.lit(1))
        .otherwise(pl.lit(-1))
    )

    return [
        z_score.fill_nan(0).fill_null(0).round(3).alias(f"{indicator_str}__z_score"),
        direction.alias(f"{indicator_str}__direction")
    ]

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    Legacy fallback for Pandas-only environments.
    """
    try:
        period = int(options.get('period', 20))
    except (ValueError, TypeError):
        period = 20

    try:
        sample_val = df['close'].iloc[0]
        sample_price = f"{sample_val:.10f}".rstrip('0')
        precision = len(sample_price.split('.')[1])+1 if '.' in sample_price else 3
        precision = min(max(precision, 2), 4) 
    except (IndexError, AttributeError, ValueError):
        precision = 3

    mean = df['close'].rolling(window=period).mean()
    std_dev = df['close'].rolling(window=period).std()
    
    z_score = (df['close'] - mean) / std_dev.replace(0, np.nan)
    direction = np.where(z_score > z_score.shift(1), 1, -1)

    res = pd.DataFrame({
        'z_score': z_score.round(precision),
        'direction': direction
    }, index=df.index)
    
    return res.dropna(subset=['z_score'])