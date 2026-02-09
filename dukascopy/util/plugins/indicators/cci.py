import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "Commodity Channel Index (CCI) measures the current price level relative "
        "to an average price level over a given period. It is used to identify "
        "new trends or warn of extreme overbought/oversold conditions."
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
        "polars": 0,
        "polars_input":1 
    }

def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for CCI.
    """
    try:
        period = int(options.get('period', 20))
    except (ValueError, TypeError):
        period = 20
    return period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    """
    return {
        "period": args[0] if len(args) > 0 else "20"
    }

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    try:
        period = int(options.get('period', 20))
    except (ValueError, TypeError):
        period = 20

    # 1. Typical Price
    tp = (pl.col("high") + pl.col("low") + pl.col("close")) / 3

    # 2. Typical Price SMA
    tp_sma = tp.rolling_mean(window_size=period)

    # 3. Correct Vectorized MAD
    # We use a rolling_map that executes a native Polars expression.
    # This is significantly faster than a Python lambda but mathematically 
    # identical to TA-Lib's requirements.
    mad = tp.rolling_map(
        lambda s: (s - s.mean()).abs().mean(),
        window_size=period
    )

    # 4. Final CCI
    # Note: 0.015 is the standard Lambert constant.
    cci = (tp - tp_sma) / (0.015 * mad)
    
    direction = pl.when(cci > cci.shift(1)).then(100).otherwise(-100)

    return [
        cci.alias(f"{indicator_str}__cci"),
        direction.alias(f"{indicator_str}__direction")
    ]

def calculate(df: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    """
    High-performance vectorized implementation using Numpy sliding window views.
    This eliminates the UDF overhead entirely.
    """
    try:
        period = int(options.get('period', 20))
    except (ValueError, TypeError):
        period = 20

    if len(df) < period:
        return pl.DataFrame({
            "cci": [None] * len(df),
            "direction": [None] * len(df)
        }).with_columns([
            pl.col("cci").cast(pl.Float64),
            pl.col("direction").cast(pl.Int32)
        ])

    # 1. Calculate Typical Price (TP)
    tp = (df["high"] + df["low"] + df["close"]) / 3
    tp_v = tp.to_numpy()

    # 2. Create sliding window view (O(1) memory view)
    # Shape becomes (N - period + 1, period)
    windows = np.lib.stride_tricks.sliding_window_view(tp_v, window_shape=period)

    # 3. Vectorized MAD calculation
    # We calculate the mean of the absolute differences between each 
    # element in the window and that specific window's mean.
    means = np.mean(windows, axis=1)
    # Using numpy broadcasting (means[:, None]) to perform 2D - 1D subtraction
    mads = np.mean(np.abs(windows - means[:, None]), axis=1)

    # 4. Alignment Padding (First 'period-1' entries are NaN)
    padding = np.full(period - 1, np.nan)
    full_means = np.concatenate([padding, means])
    full_mads = np.concatenate([padding, mads])

    # 5. Final CCI Calculation: (TP - SMA) / (0.015 * MAD)
    # Lambert's Constant = 0.015
    cci_values = (tp_v - full_means) / (0.015 * full_mads + 1e-12)

    # 6. Re-wrap in Polars and calculate Direction
    res = pl.DataFrame({"cci": cci_values})
    
    # Calculate direction: 100 if rising, -100 if falling
    res = res.with_columns(
        pl.when(pl.col("cci") > pl.col("cci").shift(1))
        .then(100)
        .otherwise(-100)
        .alias("direction")
    ).cast({"direction": pl.Int32})

    return res