import pandas as pd
import numpy as np
from typing import List, Dict, Any

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: williamsr_14 -> {'period': '14'}
    """
    return {
        "period": args[0] if len(args) > 0 else "14"
    }

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    High-performance vectorized Williams %R calculation.
    Formula: %R = (Highest High - Close) / (Highest High - Lowest Low) * -100
    """
    # 1. Parse Parameters
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14

    # 2. Determine Price Precision
    try:
        sample_val = df['close'].iloc[0]
        sample_price = f"{sample_val:.10f}".rstrip('0')
        precision = len(sample_price.split('.')[1]) if '.' in sample_price else 2
        precision = min(max(precision, 2), 8) 
    except (IndexError, AttributeError, ValueError):
        precision = 2

    # 3. Vectorized Calculation Logic
    # Get rolling high and low over the lookback period
    hh = df['high'].rolling(window=period).max()
    ll = df['low'].rolling(window=period).min()
    
    # Range calculation (Highest High - Lowest Low)
    # Handle division by zero for flat price action (HH == LL)
    range_diff = (hh - ll).replace(0, np.nan)
    
    # Williams %R Formula
    williams_r = ((hh - df['close']) / range_diff) * -100

    # 4. Final Formatting and Rounding
    # Preserving the original index for O(1) merging in parallel.py
    res = pd.DataFrame({
        'williams_r': williams_r.round(precision)
    }, index=df.index)
    
    # Drop rows where the window hasn't filled (warm-up period)
    return res.dropna(subset=['williams_r'])