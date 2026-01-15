import pandas as pd
import numpy as np
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "Bollinger Bands (BBands) are a volatility indicator consisting of a "
        "Simple Moving Average (mid) and two standard deviation lines (upper and lower). "
        "They expand during high volatility and contract during low volatility."
    )

def meta()->Dict:
    """
    Any other metadata to pass via API
    """
    return {
        "author": "Google Gemini",
        "version": 1.0,
        "panel": 0,
        "verified": 1
    }
    
def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for Bollinger Bands.
    BBands require a full 'period' to calculate the rolling mean and 
    standard deviation. We use 3x period for stability.
    """
    try:
        period = int(options.get('period', 20))
    except (ValueError, TypeError):
        period = 20

    # Matches the stabilization buffer used in sma.py
    return period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "period": args[0] if len(args) > 0 else "20",
        "std": args[1] if len(args) > 1 else "2.0"
    }

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    try:
        period = int(options.get('period', 20))
        std_dev = float(options.get('std', 2.0))
    except (ValueError, TypeError):
        period, std_dev = 20, 2.0

    mid = df['close'].rolling(window=period).mean()
    rolling_std = df['close'].rolling(window=period).std()
    
    upper = mid + (rolling_std * std_dev)
    lower = mid - (rolling_std * std_dev)

    sample_price = str(df['close'].iloc[0])
    precision = len(sample_price.split('.')[1]) if '.' in sample_price else 5
    
    res = pd.DataFrame({
        'upper': upper.round(precision),
        'mid': mid.round(precision),
        'lower': lower.round(precision)
    }, index=df.index)
    
    return res.dropna()