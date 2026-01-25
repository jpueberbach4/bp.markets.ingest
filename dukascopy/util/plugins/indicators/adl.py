import pandas as pd
import numpy as np
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "Accumulation/Distribution Line (ADL) is a volume-based indicator that "
        "measures the cumulative flow of money into and out of an asset. It assesses "
        "buying and selling pressure by looking at where the price closes relative "
        "to its high-low range for the period."
    )

def meta()->Dict:
    """
    Any other metadata to pass via API
    """
    return {
        "author": "Google Gemini",
        "version": 1.0,
        "panel":1,
        "verified": 1
    }

def warmup_count(options: Dict[str, Any]) -> int:
    """
    ADL is a cumulative indicator. While it doesn't have a fixed window,
    a warmup period ensures the indicator has enough history to show
    a meaningful trend relative to the requested start time.
    """
    # A standard default for cumulative indicators to establish trend
    return 100

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    ADL currently does not use parameters, but this is required 
    for compatibility with the parallel engine.
    """
    return {}

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    High-performance vectorized Accumulation/Distribution Line (ADL) calculation.
    
    Calculation Logic:
    1. Money Flow Multiplier (MFM) = [(Close - Low) - (High - Close)] / (High - Low)
    2. Money Flow Volume (MFV) = MFM * Volume
    3. ADL = Cumulative Sum of MFV
    """
    # 1. Determine Price Precision for rounding based on input data
    try:
        sample_price = str(df['close'].iloc[0])
        precision = len(sample_price.split('.')[1])+1 if '.' in sample_price else 2
    except (IndexError, AttributeError):
        precision = 2

    # 2. Money Flow Multiplier (MFM)
    # Handle division by zero for flat bars (where High == Low) by replacing 0 with NaN
    h_l_range = (df['high'] - df['low']).replace(0, np.nan)
    mfm = ((df['close'] - df['low']) - (df['high'] - df['close'])) / h_l_range
    
    # Fill NaN values (from flat bars) with 0 as they contribute no price movement
    mfm = mfm.fillna(0)
    
    # 3. Money Flow Volume (MFV)
    mfv = mfm * df['volume']
    
    # 4. Accumulation/Distribution Line (Cumulative Sum)
    # ADL is a running total; the parallel engine ensures the data is sorted chronologically
    adl = mfv.cumsum().round(precision)

    # 5. Return only the result column with the original index
    # This allows the parallel engine to perform a high-speed O(1) join
    return pd.DataFrame({'adl': adl}, index=df.index)