import polars as pl
import pandas as pd
import numpy as np
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "The Schaff Trend Cycle (STC) is a high-speed oscillator that combines the "
        "benefits of MACD and slow Stochastics. By applying a double-smoothed "
        "stochastic process to MACD values, it identifies market trends and "
        "cyclical turns much faster than traditional indicators. It is designed "
        "to stay at extreme levels (0 or 100) during strong trends and provide "
        "early warnings of trend exhaustion through its rapid 'cycle' movement."
    )

def meta() -> Dict:
    """
    Metadata for the dual-engine orchestrator.
    """
    return {
        "author": "Google Gemini",
        "version": 1.1,
        "panel": 1,
        "verified": 1,
        "polars": 0  # TODO: polars works but is slower than pandas variant. hence enable pandas.
    }

def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for the Schaff Trend Cycle.
    """
    try:
        slow = int(options.get('slow', 50))
    except (ValueError, TypeError):
        slow = 50
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

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    """
    High-performance Polars-native calculation for STC.
    Replicates the double-stochastic MACD smoothing logic.
    """
    try:
        cycle = int(options.get('cycle', 10))
        fast = int(options.get('fast', 23))
        slow = int(options.get('slow', 50))
    except (ValueError, TypeError):
        cycle, fast, slow = 10, 23, 50

    smooth_span = max(1, int(cycle / 2))

    # A. MACD Line
    ema_fast = pl.col("close").ewm_mean(span=fast, adjust=False)
    ema_slow = pl.col("close").ewm_mean(span=slow, adjust=False)
    macd = ema_fast - ema_slow

    # Helper for Stochastic calculation in Polars
    def polars_stoch(expr, window):
        low_min = expr.rolling_min(window_size=window)
        high_max = expr.rolling_max(window_size=window)
        return (100 * (expr - low_min) / (high_max - low_min)).fill_nan(0).fill_null(0)

    # B. First Smoothing
    stoch_1 = polars_stoch(macd, cycle)
    smooth_1 = stoch_1.ewm_mean(span=smooth_span, adjust=False)

    # C. Second Smoothing
    stoch_2 = polars_stoch(smooth_1, cycle)
    stc = stoch_2.ewm_mean(span=smooth_span, adjust=False)

    # D. Directional Slope
    direction = (
        pl.when(stc > stc.shift(1))
        .then(pl.lit(1))
        .otherwise(pl.lit(-1))
    )

    return [
        stc.round(2).alias(f"{indicator_str}__stc"),
        direction.alias(f"{indicator_str}__direction")
    ]

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    Legacy fallback for Pandas-only environments.
    """
    try:
        cycle = int(options.get('cycle', 10))
        fast = int(options.get('fast', 23))
        slow = int(options.get('slow', 50))
    except (ValueError, TypeError):
        cycle, fast, slow = 10, 23, 50

    ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow

    def get_stoch(series, window):
        low_min = series.rolling(window=window).min()
        high_max = series.rolling(window=window).max()
        denom = (high_max - low_min).replace(0, np.nan)
        return 100 * (series - low_min) / denom

    smooth_span = max(1, int(cycle / 2))
    
    stoch_1 = get_stoch(macd, cycle).fillna(0)
    smooth_1 = stoch_1.ewm(span=smooth_span, adjust=False).mean()

    stoch_2 = get_stoch(smooth_1, cycle).fillna(0)
    stc = stoch_2.ewm(span=smooth_span, adjust=False).mean()

    direction = np.where(stc > stc.shift(1), 1, -1)

    res = pd.DataFrame({
        'stc': stc.round(2),
        'direction': direction
    }, index=df.index)
    
    warmup = slow + (cycle * 2)
    return res.iloc[warmup:]