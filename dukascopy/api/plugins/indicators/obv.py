import pandas as pd
import numpy as np
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "On-Balance Volume (OBV) is a technical indicator that uses volume flow "
        "to predict changes in stock price. It relates price momentum to trading "
        "volume, acting as a cumulative total of volume: adding volume on up days "
        "and subtracting it on down days. It is primarily used to confirm trends "
        "or spot potential reversals through price-volume divergence."
    )

def meta()->Dict:
    """
    Any other metadata to pass via API
    """
    return {
        "author": "Google Gemini",
        "version": 1.0,
        "panel": 1
    }
    
def warmup_count(options: Dict[str, Any]) -> int:
    """
    OBV is a cumulative indicator. 
    A warmup period ensures the volume trend is established 
    before the user's requested start date.
    """
    # 100 bars is a standard buffer to establish a stable volume trend
    return 100

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    OBV typically takes no parameters.
    """
    return {}

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    High-performance vectorized On-Balance Volume (OBV) calculation.
    Formula: 
    If Close > PrevClose: OBV = PrevOBV + Volume
    If Close < PrevClose: OBV = PrevOBV - Volume
    If Close == PrevClose: OBV = PrevOBV
    """
    
    # 1. Calculation Logic
    # Calculate price change (vectorized)
    close_diff = df['close'].diff()
    
    # Determine direction: 1 for up, -1 for down, 0 for flat (Vectorized)
    # Using np.where is significantly faster than .apply() for large datasets
    direction = np.where(close_diff > 0, 1, np.where(close_diff < 0, -1, 0))
    
    # Calculate OBV using cumulative sum
    # OBV is inherently path-dependent, so we use .cumsum() which is optimized in C
    obv = (direction * df['volume']).cumsum()

    # 2. Final Formatting and Rounding
    # OBV represents Volume. We round to 2 decimals to accommodate crypto/fractional volume.
    # Preserving the original index for O(1) merging in parallel.py
    res = pd.DataFrame({
        'obv': obv.round(2)
    }, index=df.index)
    
    # Fill the first row (NaN from .diff()) with 0 or the first volume bar
    res['obv'] = res['obv'].fillna(0)
    
    return res