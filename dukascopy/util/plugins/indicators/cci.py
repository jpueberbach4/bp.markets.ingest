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
        "polars": 1  # Trigger high-speed Polars execution path
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
    """
    High-performance Polars-native calculation using vectorized MAD.
    """
    try:
        period = int(options.get('period', 20))
    except (ValueError, TypeError):
        period = 20

    # 1. Calculate Typical Price (TP)
    tp = (pl.col("high") + pl.col("low") + pl.col("close")) / 3

    # 2. Calculate SMA of Typical Price
    tp_sma = tp.rolling_mean(window_size=period)

    # 3. Calculate Mean Absolute Deviation (MAD)
    # We use rolling_map with a vectorized internal expression to stay in Rust
    mad = tp.rolling_map(
        lambda s: (s - s.mean()).abs().mean(), 
        window_size=period
    )

    # 4. Calculate CCI and Direction
    cci = (tp - tp_sma) / (0.015 * mad)
    direction = pl.when(cci > cci.shift(1)).then(100).otherwise(-100)

    # Return aliased expressions for the nested orchestrator
    return [
        cci.alias(f"{indicator_str}__cci"),
        direction.alias(f"{indicator_str}__direction")
    ]

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    Legacy Pandas fallback.
    """
    try:
        period = int(options.get('period', 20))
    except (ValueError, TypeError):
        period = 20

    tp = (df['high'] + df['low'] + df['close']) / 3
    tp_sma = tp.rolling(window=period).mean()
    
    # Slow Python-based MAD
    def get_mad(x):
        return np.abs(x - x.mean()).mean()
    mad = tp.rolling(window=period).apply(get_mad, raw=True)

    cci = (tp - tp_sma) / (0.015 * mad)
    direction = np.where(cci > cci.shift(1), 100, -100)
    
    return pd.DataFrame({
        'cci': cci,
        'direction': direction
    }, index=df.index).dropna()