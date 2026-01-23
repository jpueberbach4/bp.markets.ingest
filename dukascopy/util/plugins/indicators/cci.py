import pandas as pd
import numpy as np
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "Commodity Channel Index (CCI) is a versatile indicator that can be used to "
        "identify a new trend or warn of extreme conditions. It measures the current "
        "price level relative to an average price level over a given period of time. "
        "CCI is relatively high when prices are far above their average and relatively "
        "low when prices are far below their average."
    )

def meta()->Dict:
    """
    Any other metadata to pass via API
    """
    return {
        "author": "Google Gemini",
        "version": 1.0,
        "panel": 1,
        "verified": 1
    }
    
def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for CCI.
    CCI requires a full 'period' to calculate the Typical Price SMA 
    and Mean Absolute Deviation. We use 3x period for stability.
    """
    try:
        period = int(options.get('period', 20))
    except (ValueError, TypeError):
        period = 20

    # Consistent with SMA and BBands stabilization buffer
    return period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: cci_20 -> {'period': '20'}
    """
    return {
        "period": args[0] if len(args) > 0 else "20"
    }

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    High-performance vectorized Commodity Channel Index (CCI) calculation.
    Formula: (Typical Price - SMA of TP) / (0.015 * Mean Absolute Deviation)
    """
    # 1. Parse Parameters
    try:
        period = int(options.get('period', 20))
    except (ValueError, TypeError):
        period = 20

    # 2. Determine Price Precision for rounding
    try:
        sample_price = str(df['close'].iloc[0])
        precision = len(sample_price.split('.')[1])+1 if '.' in sample_price else 2
    except (IndexError, AttributeError):
        precision = 5

    # 3. Calculate Typical Price (TP)
    tp = (df['high'] + df['low'] + df['close']) / 3
    
    # 4. Calculate SMA of Typical Price
    tp_sma = tp.rolling(window=period).mean()
    
    # 5. Calculate Mean Absolute Deviation (MAD)
    # Using a vectorized rolling window apply with raw=True for speed
    def get_mad(x):
        return np.abs(x - x.mean()).mean()
    
    mad = tp.rolling(window=period).apply(get_mad, raw=True)

    # 6. Calculate CCI
    # The 0.015 constant ensures most values fall between -100 and +100
    cci = (tp - tp_sma) / (0.015 * mad)
    
    # 7. Directional slope (1 for up, -1 for down)
    direction = np.where(cci > cci.shift(1), 1, -1)

    # 8. Final Formatting and Rounding
    res = pd.DataFrame({
        'cci': cci.round(precision),
        'direction': direction*100
    }, index=df.index)
    
    # Drop rows where the window hasn't filled (warmup period)
    return res.dropna(subset=['cci'])