import pandas as pd
import numpy as np
from typing import List, Dict, Any

def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for MACD.
    MACD uses two recursive EMAs (Fast/Slow) and then a third (Signal).
    We use 3x the slow_period to ensure all three have converged.
    """
    try:
        slow_period = int(options.get('slow', 26))
    except (ValueError, TypeError):
        slow_period = 26

    # 3x the longest period (slow) is the standard for EMA convergence
    return slow_period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: macd_12_26_9 -> {'fast': '12', 'slow': '26', 'signal': '9'}
    """
    return {
        "fast": args[0] if len(args) > 0 else "12",
        "slow": args[1] if len(args) > 1 else "26",
        "signal": args[2] if len(args) > 2 else "9"
    }

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    High-performance vectorized Moving Average Convergence Divergence (MACD).
    """
    # 1. Parse Parameters
    try:
        fast = int(options.get('fast', 12))
        slow = int(options.get('slow', 26))
        signal = int(options.get('signal', 9))
    except (ValueError, TypeError):
        fast, slow, signal = 12, 26, 9

    # 2. Determine Price Precision for rounding
    try:
        sample_price = str(df['close'].iloc[0])
        precision = len(sample_price.split('.')[1]) if '.' in sample_price else 2
    except (IndexError, AttributeError):
        precision = 5

    # 3. Vectorized Calculation Logic
    # Fast and Slow EMAs
    ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
    
    # MACD Line
    macd_line = ema_fast - ema_slow
    
    # Signal Line (EMA of the MACD Line)
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    
    # Histogram
    hist = macd_line - signal_line

    # 4. Final Formatting and Rounding
    # Preserving the original index for O(1) merging in the parallel engine
    res = pd.DataFrame({
        'macd': macd_line.round(precision),
        'signal': signal_line.round(precision),
        'hist': hist.round(precision)
    }, index=df.index)
    
    # Drop the warm-up period rows where the slow EMA hasn't stabilized
    return res.dropna(subset=['macd']).iloc[slow:]