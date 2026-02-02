import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "Shannon Entropy measures the complexity and unpredictability of price "
        "movements by analyzing the distribution of price returns. A higher entropy "
        "value suggests a more chaotic or random market state (high uncertainty), "
        "while lower values indicate more ordered, predictable patterns. The 'Efficiency' "
        "metric normalizes this value between 0 and 1, where 1 represents a perfectly "
        "ordered state and 0 represents maximum market chaos."
    )

def meta() -> Dict:
    """
    Metadata for the dual-engine orchestrator.
    """
    return {
        "author": "Google Gemini",
        "version": 1.3,
        "panel": 1,
        "verified": 1,
        "polars": 0     # TODO: pandas version is faster, however, newer polars version fixes it. 
    }

def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for Shannon Entropy.
    """
    try:
        period = int(options.get('period', 20))
    except (ValueError, TypeError):
        period = 20
    return period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: shannonentropy_20_10 -> {'period': '20', 'bins': '10'}
    """
    return {
        "period": args[0] if len(args) > 0 else "20",
        "bins": args[1] if len(args) > 1 else "10"
    }

def _calc_entropy_only(y: np.ndarray, bins: int) -> float:
    """
    Optimized UDF: Calculates ONLY Entropy.
    Efficiency is derived mathematically in the Polars graph to save CPU.
    """
    # Create returns inside the window to match Legacy Pandas logic
    # Note: This is a Python loop inside Polars (unavoidable for histograms without custom Rust plugins)
    returns = np.diff(y)
    
    if len(returns) == 0:
        return 0.0
        
    # Histogram is the most expensive part
    counts, _ = np.histogram(returns, bins=bins)
    
    # Filter non-zero probabilities to allow log2 calculation
    probs = counts / np.sum(counts)
    probs = probs[probs > 0] 
    
    # Shannon Entropy Formula: -Sum(p * log2(p))
    return -np.sum(probs * np.log2(probs))

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    """
    High-performance Polars-native calculation for Shannon Entropy.
    """
    try:
        period = int(options.get('period', 20))
        bins = int(options.get('bins', 10))
    except (ValueError, TypeError):
        period, bins = 20, 10

    # 1. Calculate max entropy constant for this configuration
    # H_max = log2(bins)
    max_entropy = np.log2(bins) if bins > 0 else 1.0

    # 2. Define the Entropy Expression
    # We remove 'return_dtype' from rolling_map as it's not supported there.
    # Instead, we cast the result immediately after.
    entropy_expr = (
        pl.col("close")
        .cast(pl.Float64)
        .rolling_map(
            lambda s: _calc_entropy_only(s.to_numpy(), bins),
            window_size=period
        ).cast(pl.Float64) # Explicit cast handles the type safety
    )

    # 3. Derive Efficiency Expression (Zero-Cost Vectorized Operation)
    # Efficiency = 1 - (Entropy / Max_Entropy)
    efficiency_expr = (1.0 - (entropy_expr / max_entropy)).clip(0.0, 1.0)

    # 4. Return both expressions
    return [
        entropy_expr.round(4).alias(f"{indicator_str}__entropy"),
        efficiency_expr.round(4).alias(f"{indicator_str}__efficiency")
    ]

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    Legacy fallback for Pandas-only environments.
    """
    try:
        period = int(options.get('period', 20))
        bins = int(options.get('bins', 10))
    except (ValueError, TypeError):
        period, bins = 20, 10

    def get_entropy_stats(y: np.ndarray, bins: int):
        returns = np.diff(y)
        if len(returns) == 0: return 0.0, 1.0
        counts, _ = np.histogram(returns, bins=bins)
        probs = counts / np.sum(counts)
        probs = probs[probs > 0]
        entropy = -np.sum(probs * np.log2(probs))
        max_entropy = np.log2(bins)
        efficiency = 1.0 - (entropy / max_entropy) if max_entropy > 0 else 1.0
        return entropy, np.clip(efficiency, 0, 1)

    # Legacy double-calculation (Pandas)
    entropy_raw = df['close'].rolling(window=period).apply(
        lambda x: get_entropy_stats(x, bins)[0], raw=True
    )
    efficiency_raw = df['close'].rolling(window=period).apply(
        lambda x: get_entropy_stats(x, bins)[1], raw=True
    )

    res = pd.DataFrame({
        'entropy': entropy_raw.round(4),
        'efficiency': efficiency_raw.round(4)
    }, index=df.index)
    
    return res.dropna(subset=['entropy'])