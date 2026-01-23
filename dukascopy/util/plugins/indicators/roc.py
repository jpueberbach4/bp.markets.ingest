import pandas as pd
import numpy as np
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "The Rate of Change (ROC) is a pure momentum oscillator that measures the "
        "percentage change in price between the current period and a specific "
        "number of periods ago. It fluctuates above and below a Zero Line; "
        "positive values indicate bullish momentum, while negative values indicate "
        "bearish momentum. It is widely used to identify trend strength, "
        "overbought/oversold conditions, and momentum divergences."
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
    Calculates the required warmup rows for Rate of Change (ROC).
    Requires 'period' rows to find the historical price comparison.
    We use 3x period for stability and engine consistency.
    """
    try:
        period = int(options.get('period', 9))
    except (ValueError, TypeError):
        period = 9

    # Consistent with other rolling-window stabilization buffers
    return period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: roc_12 -> {'period': '12'}
    """
    return {
        "period": args[0] if len(args) > 0 else "9"
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