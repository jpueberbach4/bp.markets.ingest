import pandas as pd
import numpy as np
from typing import List, Dict, Any

def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for the EMA.
    EMA is a recursive calculation that requires history to stabilize.
    We use 3x the period as the industry standard for convergence.
    """
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14

    # 3x period ensures the initial seed value has decayed 
    # and the EMA is mathematically accurate.
    return period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: ema_50 -> {'period': '50'}
    """
    return {
        "period": args[0] if len(args) > 0 else "14"
    }

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    High-performance vectorized Exponential Moving Average (EMA) calculation.
    """
    # 1. Parse Parameters
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14

    # 2. Determine Price Precision for rounding
    try:
        # Detect decimals from the first available close price
        sample_price = str(df['close'].iloc[0])
        precision = len(sample_price.split('.')[1]) if '.' in sample_price else 2
    except (IndexError, AttributeError):
        precision = 5

    # 3. Vectorized EMA Calculation
    # adjust=False ensures we use the standard recursive EMA formula 
    # (suitable for technical analysis matching MT4/TradingView)
    ema = df['close'].ewm(span=period, adjust=False).mean()

    # 4. Final Formatting and Rounding
    # Preserving the original index for O(1) merging in the parallel engine
    res = pd.DataFrame({
        'ema': ema.round(precision)
    }, index=df.index)
    
    # Drop the warm-up period rows where the EMA hasn't stabilized
    return res.dropna(subset=['ema']).iloc[period:]