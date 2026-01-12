import pandas as pd
import numpy as np
from typing import List, Dict, Any

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: zscore_20 -> {'period': '20'}
    """
    return {
        "period": args[0] if len(args) > 0 else "20"
    }

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    High-performance vectorized Z-Score (Standard Score).
    Formula: Z = (Price - Mean) / StdDev
    """
    # 1. Parse Parameters
    try:
        period = int(options.get('period', 20))
    except (ValueError, TypeError):
        period = 20

    # 2. Determine Price Precision
    # Z-Score is a statistical ratio, usually 3 decimals are sufficient
    try:
        sample_val = df['close'].iloc[0]
        sample_price = f"{sample_val:.10f}".rstrip('0')
        precision = len(sample_price.split('.')[1]) if '.' in sample_price else 2
        # For Z-score, we clamp between 2 and 4 to maintain readability
        precision = min(max(precision, 2), 4) 
    except (IndexError, AttributeError, ValueError):
        precision = 3

    # 3. Vectorized Calculation Logic
    # Calculate rolling mean and standard deviation
    mean = df['close'].rolling(window=period).mean()
    std_dev = df['close'].rolling(window=period).std()
    
    # Calculate Z-Score
    # Handle division by zero for flat markets (std_dev == 0)
    z_score = (df['close'] - mean) / std_dev.replace(0, np.nan)

    # 4. Directional Slope
    # 1 for increasing score, -1 for decreasing
    direction = np.where(z_score > z_score.shift(1), 1, -1)

    # 5. Final Formatting and Rounding
    # Preserving the original index for O(1) merging in parallel.py
    res = pd.DataFrame({
        'z_score': z_score.round(precision),
        'direction': direction
    }, index=df.index)
    
    # Drop rows where the window hasn't filled (warm-up period)
    return res.dropna(subset=['z_score'])