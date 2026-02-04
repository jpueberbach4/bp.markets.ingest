import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "Chande Momentum Oscillator (CMO) measures the difference between recent "
        "gains and losses. This implementation matches the TA-Lib C-standard by "
        "using Wilder's Smoothing (EMA-based) rather than simple rolling sums."
    )

def meta() -> Dict:
    return {
        "author": "Google Gemini",
        "version": 1.2,
        "panel": 1,
        "verified": 1,
        "talib-validated": 1, 
        "polars": 1
    }

def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "period": args[0] if len(args) > 0 else "14"
    }

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> pl.Expr:
    """
    Polars implementation aligned with TA-Lib C-math.
    Uses EWM (Wilder's Smoothing) to match TA-Lib's CMO.
    """
    try:
        p = int(options.get('period', 14))
    except (ValueError, TypeError):
        p = 14

    diff = pl.col("close").diff()

    gain = pl.when(diff > 0).then(diff).otherwise(0.0)
    loss = pl.when(diff < 0).then(diff.abs()).otherwise(0.0)

    sm_g = gain.ewm_mean(span=2 * p - 1, adjust=False)
    sm_l = loss.ewm_mean(span=2 * p - 1, adjust=False)

    cmo = (100 * (sm_g - sm_l) / (sm_g + sm_l))

    return cmo.alias(indicator_str)

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    Pandas fallback aligned with TA-Lib.
    """
    try:
        p = int(options.get('period', 14))
    except (ValueError, TypeError):
        p = 14

    delta = df['close'].diff()
    gains = delta.where(delta > 0, 0.0)
    losses = delta.where(delta < 0, 0.0).abs()
    
    avg_g = gains.ewm(com=p - 1, adjust=False).mean()
    avg_l = losses.ewm(com=p - 1, adjust=False).mean()
    
    cmo_values = 100 * ((avg_g - avg_l) / (avg_g + avg_l))
    
    return pd.DataFrame({'cmo': cmo_values}, index=df.index)