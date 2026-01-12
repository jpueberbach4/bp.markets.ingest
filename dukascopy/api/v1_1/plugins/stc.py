import pandas as pd
import numpy as np
from typing import List, Dict, Any

def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for the Schaff Trend Cycle.
    STC is highly sensitive as it involves MACD EMAs, two rolling 
    stochastic windows, and final EMA smoothing.
    We use 3x the slow MACD period to ensure all layers converge.
    """
    try:
        slow = int(options.get('slow', 50))
    except (ValueError, TypeError):
        slow = 50

    # 3x the longest recursive component (slow MACD) provides
    # the necessary runway for the double-stochastic to stabilize.
    return slow * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: stc_10_23_50 -> {'cycle': '10', 'fast': '23', 'slow': '50'}
    """
    return {
        "cycle": args[0] if len(args) > 0 else "10",
        "fast": args[1] if len(args) > 1 else "23",
        "slow": args[2] if len(args) > 2 else "50"
    }

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    High-performance vectorized Schaff Trend Cycle (STC).
    Formula: EMA smoothed double-stochastic of MACD.
    """
    # 1. Parse Parameters
    try:
        cycle = int(options.get('cycle', 10))
        fast = int(options.get('fast', 23))
        slow = int(options.get('slow', 50))
    except (ValueError, TypeError):
        cycle, fast, slow = 10, 23, 50

    # 2. Vectorized Calculation Logic
    # A. MACD Line
    ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow

    # Helper for Stochastic calculation
    def get_stoch(series, window):
        low_min = series.rolling(window=window).min()
        high_max = series.rolling(window=window).max()
        denom = (high_max - low_min).replace(0, np.nan)
        return 100 * (series - low_min) / denom

    smooth_span = max(1, int(cycle / 2))
    
    # B. First Smoothing (Stochastic of MACD)
    stoch_1 = get_stoch(macd, cycle).fillna(0)
    smooth_1 = stoch_1.ewm(span=smooth_span, adjust=False).mean()

    # C. Second Smoothing (Stochastic of first smooth)
    stoch_2 = get_stoch(smooth_1, cycle).fillna(0)
    stc = stoch_2.ewm(span=smooth_span, adjust=False).mean()

    # 3. Final Formatting and Rounding
    # Directional slope (1 for up, -1 for down)
    direction = np.where(stc > stc.shift(1), 1, -1)

    # Preserving the original index for O(1) merging in parallel.py
    res = pd.DataFrame({
        'stc': stc.round(2),
        'direction': direction
    }, index=df.index)
    
    # Drop warm-up rows (MACD slow period + double cycle)
    warmup = slow + (cycle * 2)
    return res.iloc[warmup:]