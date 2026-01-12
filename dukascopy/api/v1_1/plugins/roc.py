import pandas as pd
import numpy as np
from typing import List, Dict, Any

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: roc_12 -> {'period': '12'}
    """
    return {
        "period": args[0] if len(args) > 0 else "12"
    }

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    High-performance vectorized Rate of Change (ROC) calculation.
    ROC = ((Price - Price_n) / Price_n) * 100
    """
    # 1. Parse Parameters
    try:
        period = int(options.get('period', 12))
    except (ValueError, TypeError):
        period = 12

    # 2. Determine Precision
    # Momentum indicators are typically rounded to 2 or 3 decimals
    precision = 3 

    # 3. Vectorized Calculation Logic
    # Shift price by n periods to get 'Price_n'
    price_n = df['close'].shift(period)
    
    # Calculate ROC percentage change
    # Handle division by zero using .replace(0, np.nan)
    roc = ((df['close'] - price_n) / price_n.replace(0, np.nan)) * 100

    # 4. Final Formatting and Rounding
    # Preserving the original index for O(1) merging in parallel.py
    res = pd.DataFrame({
        'roc': roc.round(precision)
    }, index=df.index)
    
    # Drop rows where the shifting period hasn't filled (warm-up period)
    return res.dropna(subset=['roc'])