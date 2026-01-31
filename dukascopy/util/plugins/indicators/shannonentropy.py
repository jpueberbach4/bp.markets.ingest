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
        "version": 1.1,
        "panel": 1,
        "verified": 1,
        "polars": 1  # Flag to trigger high-speed Polars execution
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

def _entropy_backend(y: np.ndarray, bins: int) -> np.ndarray:
    """
    Internal NumPy engine to calculate Shannon stats for a sliding window.
    Returns [entropy, efficiency].
    """
    returns = np.diff(y)
    if len(returns) == 0:
        return np.array([0.0, 1.0])
        
    counts, _ = np.histogram(returns, bins=bins)
    probs = counts / np.sum(counts)
    probs = probs[probs > 0] 
    
    entropy = -np.sum(probs * np.log2(probs))
    max_entropy = np.log2(bins)
    efficiency = 1.0 - (entropy / max_entropy) if max_entropy > 0 else 1.0
    
    return np.array([entropy, np.clip(efficiency, 0, 1)])

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    """
    High-performance Polars-native calculation for Shannon Entropy.
    """
    try:
        period = int(options.get('period', 20))
        bins = int(options.get('bins', 10))
    except (ValueError, TypeError):
        period, bins = 20, 10

    # Calculate both metrics in a single struct-mapped rolling window
    stats = pl.col("close").rolling_map(
        lambda s: _entropy_backend(s.to_numpy(), bins),
        window_size=period
    )

    return [
        stats.map_elements(lambda x: x[0], return_dtype=pl.Float64).round(4).alias(f"{indicator_str}__entropy"),
        stats.map_elements(lambda x: x[1], return_dtype=pl.Float64).round(4).alias(f"{indicator_str}__efficiency")
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