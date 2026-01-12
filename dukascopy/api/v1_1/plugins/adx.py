import pandas as pd
import numpy as np
from typing import List, Dict, Any

def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for ADX.
    ADX uses Wilder's Smoothing (EWM) and requires roughly 3x the period 
    to provide stabilized values.
    """
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14

    # Wilder's smoothing needs a longer tail to converge. 
    # 3x is recommended for production-grade accuracy.
    return period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    """
    return {
        "period": args[0] if len(args) > 0 else "14"
    }

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    High-performance vectorized ADX, +DI, and -DI calculation.
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

    # 3. Calculate True Range (TR) and Directional Movement (DM)
    prev_close = df['close'].shift(1)
    prev_high = df['high'].shift(1)
    prev_low = df['low'].shift(1)
    
    tr1 = df['high'] - df['low']
    tr2 = (df['high'] - prev_close).abs()
    tr3 = (df['low'] - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    plus_dm = np.where((df['high'] - prev_high) > (prev_low - df['low']), 
                        np.maximum(df['high'] - prev_high, 0), 0)
    minus_dm = np.where((prev_low - df['low']) > (df['high'] - prev_high), 
                         np.maximum(prev_low - df['low'], 0), 0)
    
    # 4. Smooth TR and DM using Wilder's Smoothing (EWM)
    # alpha=1/period corresponds to Wilder's smoothing method
    atr_smooth = tr.ewm(alpha=1/period, min_periods=period).mean()
    plus_di_smooth = pd.Series(plus_dm, index=df.index).ewm(alpha=1/period, min_periods=period).mean()
    minus_di_smooth = pd.Series(minus_dm, index=df.index).ewm(alpha=1/period, min_periods=period).mean()
    
    # 5. Calculate +DI and -DI
    plus_di = 100 * (plus_di_smooth / atr_smooth)
    minus_di = 100 * (minus_di_smooth / atr_smooth)
    
    # 6. Calculate DX and then ADX
    di_sum = plus_di + minus_di
    dx = 100 * (plus_di - minus_di).abs() / di_sum.replace(0, np.nan)
    adx = dx.ewm(alpha=1/period, min_periods=period).mean()
    
    # 7. Final Formatting and Rounding
    res = pd.DataFrame({
        'adx': adx.round(precision),
        'plus_di': plus_di.round(precision),
        'minus_di': minus_di.round(precision)
    }, index=df.index)
    
    # Drop rows where ADX hasn't finished its warmup period
    return res.dropna()