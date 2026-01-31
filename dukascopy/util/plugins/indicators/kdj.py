import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "The KDJ Indicator is a derived version of the Stochastic Oscillator "
        "used to identify trend strength and entry points. It consists of three "
        "lines: the K (fast), the D (slow), and the J (divergence). The J line "
        "represents the divergence of the K value from the D value, often acting "
        "as a lead indicator to signal overbought or oversold conditions before "
        "they appear in the standard K and D lines."
    )

def meta()->Dict:
    """
    Metadata for the dual-engine orchestrator.
    """
    return {
        "author": "Google Gemini",
        "version": 1.1,
        "panel": 1,
        "verified": 1,
        "polars": 1  # Trigger high-speed Polars execution
    }
    
def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for KDJ.
    """
    try:
        n = int(options.get('n', 9))
    except (ValueError, TypeError):
        n = 9
    return n * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    """
    return {
        "n": args[0] if len(args) > 0 else "9",
        "m1": args[1] if len(args) > 1 else "3",
        "m2": args[2] if len(args) > 2 else "3"
    }

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    """
    High-performance Polars-native calculation for KDJ.
    Uses recursive expressions to match Pandas EWM behavior.
    """
    try:
        n = int(options.get('n', 9))
        m1 = int(options.get('m1', 3))
        m2 = int(options.get('m2', 3))
    except (ValueError, TypeError):
        n, m1, m2 = 9, 3, 3

    # 1. Calculate RSV (Raw Stochastic Value)
    # Handle flat price action by filling nulls with 50 (neutral)
    low_min = pl.col("low").rolling_min(window_size=n)
    high_max = pl.col("high").rolling_max(window_size=n)
    
    rsv = (100 * (pl.col("close") - low_min) / (high_max - low_min)).fill_nan(50).fill_null(50)

    # 2. Recursive K and D (EMA logic)
    # alpha = 1 / period is the equivalent for the KDJ recursive formula
    k = rsv.ewm_mean(alpha=1/m1, adjust=False)
    d = k.ewm_mean(alpha=1/m2, adjust=False)
    j = (3 * k) - (2 * d)

    # 3. Return as aliased expressions for parallel.py mapping
    return [
        k.round(2).alias(f"{indicator_str}__k"),
        d.round(2).alias(f"{indicator_str}__d"),
        j.round(2).alias(f"{indicator_str}__j")
    ]

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    High-performance vectorized KDJ calculation.
    K = EMA(RSV, m1), D = EMA(K, m2), J = 3K - 2D
    """
    # 1. Parse Parameters
    try:
        n = int(options.get('n', 9))      # Lookback period
        m1 = int(options.get('m1', 3))    # K slowing
        m2 = int(options.get('m2', 3))    # D slowing
    except (ValueError, TypeError):
        n, m1, m2 = 9, 3, 3

    # 2. Determine Precision
    precision = 2 # Standard for oscillators

    # 3. Calculate RSV (Raw Stochastic Value)
    low_min = df['low'].rolling(window=n).min()
    high_max = df['high'].rolling(window=n).max()
    
    # Handle division by zero for flat price action
    rsv = 100 * ((df['close'] - low_min) / (high_max - low_min).replace(0, np.nan))
    rsv = rsv.fillna(50) # Seed flat areas with neutral 50

    # 4. Vectorized K and D Calculation
    # The recursive KDJ formula is an EMA with alpha = 1/period
    # com = period - 1 is the equivalent Pandas 'com' parameter
    k = rsv.ewm(com=m1-1, adjust=False).mean()
    d = k.ewm(com=m2-1, adjust=False).mean()
    
    # 5. Calculate J Line
    j = (3 * k) - (2 * d)

    # 6. Final Formatting and Rounding
    # Preserving original index for O(1) merging in parallel.py
    res = pd.DataFrame({
        'k': k.round(precision),
        'd': d.round(precision),
        'j': j.round(precision)
    }, index=df.index)
    
    # Drop rows where the initial lookback hasn't filled
    return res.dropna(subset=['k'])