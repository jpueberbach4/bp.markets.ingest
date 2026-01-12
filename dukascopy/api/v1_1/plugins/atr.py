import pandas as pd
import numpy as np
from typing import List, Dict, Any

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: atr_14 -> {'period': '14'}
    """
    return {
        "period": args[0] if len(args) > 0 else "14"
    }

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    High-performance vectorized Average True Range (ATR) calculation.
    """
    # 1. Parse Period
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14

    # 2. Determine Price Precision for rounding
    try:
        sample_price = str(df['close'].iloc[0])
        precision = len(sample_price.split('.')[1]) if '.' in sample_price else 2
    except (IndexError, AttributeError):
        precision = 5

    # 3. Calculate True Range (TR)
    prev_close = df['close'].shift(1)
    
    tr1 = df['high'] - df['low']
    tr2 = (df['high'] - prev_close).abs()
    tr3 = (df['low'] - prev_close).abs()
    
    # Vectorized max across the three TR components
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # 4. Calculate ATR using Wilder's Smoothing
    # Wilder's Smoothing is equivalent to an EWM with alpha = 1/period
    # or com = period - 1
    atr = tr.ewm(com=period - 1, min_periods=period).mean()
    
    # 5. Final Formatting and Rounding
    res = pd.DataFrame({
        'atr': atr.round(precision)
    }, index=df.index)
    
    # Drop rows where ATR hasn't finished its warmup period
    return res.dropna()