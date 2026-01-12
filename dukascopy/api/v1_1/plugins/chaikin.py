import pandas as pd
import numpy as np
from typing import List, Dict, Any

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: chaikin_3_10 -> {'short': '3', 'long': '10'}
    """
    return {
        "short": args[0] if len(args) > 0 else "3",
        "long": args[1] if len(args) > 1 else "10"
    }

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    High-performance vectorized Chaikin Oscillator calculation.
    Formula: EMA(ADL, short) - EMA(ADL, long)
    """
    # 1. Parse Parameters
    try:
        short_period = int(options.get('short', 3))
        long_period = int(options.get('long', 10))
    except (ValueError, TypeError):
        short_period, long_period = 3, 10

    # 2. Determine Price Precision for rounding
    try:
        sample_price = str(df['close'].iloc[0])
        precision = len(sample_price.split('.')[1]) if '.' in sample_price else 2
    except (IndexError, AttributeError):
        precision = 2

    # 3. Money Flow Multiplier (MFM)
    # Handle division by zero for flat bars (High == Low)
    h_l_range = (df['high'] - df['low']).replace(0, np.nan)
    mfm = ((df['close'] - df['low']) - (df['high'] - df['close'])) / h_l_range
    mfm = mfm.fillna(0)
    
    # 4. Money Flow Volume (MFV) and Accumulation Distribution Line (ADL)
    mfv = mfm * df['volume']
    adl = mfv.cumsum()
    
    # 5. Chaikin Oscillator calculation
    # EMA(ADL, short) - EMA(ADL, long)
    ema_short = adl.ewm(span=short_period, adjust=False).mean()
    ema_long = adl.ewm(span=long_period, adjust=False).mean()
    
    chaikin = (ema_short - ema_long).round(precision)

    # 6. Return only the result column with original index
    return pd.DataFrame({'chaikin': chaikin}, index=df.index)