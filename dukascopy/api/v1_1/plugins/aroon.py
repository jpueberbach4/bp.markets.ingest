import pandas as pd
import numpy as np
from typing import List, Dict, Any

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: aroon_25 -> {'period': '25'}
    """
    return {
        "period": args[0] if len(args) > 0 else "25"
    }

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    High-performance vectorized Aroon Indicator calculation.
    """
    # 1. Parse Period
    try:
        period = int(options.get('period', 25))
    except (ValueError, TypeError):
        period = 25

    # 2. Determine Price Precision for rounding
    try:
        sample_price = str(df['close'].iloc[0])
        precision = len(sample_price.split('.')[1]) if '.' in sample_price else 2
    except (IndexError, AttributeError):
        precision = 2

    # 3. Calculation Logic
    # Aroon Up/Down = ((period - days since n-period extreme) / period) * 100
    # We use a window of period + 1 to account for the current bar
    window = period + 1
    
    # Vectorized argmax/argmin over a rolling window
    # These return the relative index (0 to period) of the high/low
    aroon_up_days = df['high'].rolling(window=window).apply(lambda x: x.argmax(), raw=True)
    aroon_down_days = df['low'].rolling(window=window).apply(lambda x: x.argmin(), raw=True)

    # Convert relative index to "days since" and calculate percentage
    # In a window of size 26, the current bar is index 25 (argmax=25 means 0 days ago)
    res_up = (aroon_up_days / period) * 100
    res_down = (aroon_down_days / period) * 100

    # 4. Final Formatting and Rounding
    res = pd.DataFrame({
        'aroon_up': res_up.round(precision),
        'aroon_down': res_down.round(precision)
    }, index=df.index)
    
    # Drop rows where the window hasn't filled yet (warmup period)
    return res.dropna()