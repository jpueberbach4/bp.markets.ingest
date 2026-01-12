import pandas as pd
import numpy as np
from typing import List, Dict, Any

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: cmo_14 -> {'period': '14'}
    """
    return {
        "period": args[0] if len(args) > 0 else "14"
    }

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    High-performance vectorized Chande Momentum Oscillator (CMO) calculation.
    Formula: 100 * (SumG - SumL) / (SumG + SumL)
    """
    # 1. Parse Parameters
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

    # 3. Calculate Price Change (Delta)
    delta = df['close'].diff()
    
    # 4. Identify Gains and Losses
    # Gains are positive changes, Losses are absolute values of negative changes
    gains = delta.where(delta > 0, 0)
    losses = delta.where(delta < 0, 0).abs()
    
    # 5. Calculate Rolling Sums
    sum_gains = gains.rolling(window=period).sum()
    sum_losses = losses.rolling(window=period).sum()
    
    # 6. Calculate CMO
    # total_movement = Sum of Gains + Sum of Losses
    total_movement = sum_gains + sum_losses
    
    # Handle division by zero for stagnant periods using replace(0, np.nan)
    cmo_values = 100 * ((sum_gains - sum_losses) / total_movement.replace(0, np.nan))
    
    # 7. Final Formatting and Rounding
    # Returns a DataFrame with the original index for O(1) merging in parallel.py
    res = pd.DataFrame({
        'cmo': cmo_values.round(precision)
    }, index=df.index)
    
    # Drop rows where the window hasn't filled (warmup period)
    return res.dropna(subset=['cmo'])