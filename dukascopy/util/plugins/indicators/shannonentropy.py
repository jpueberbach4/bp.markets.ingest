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
        "polars": 0,
        "polars_input": 1 
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

def calculate(df: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    """
    High-performance Shannon Entropy implementation for polars_input: 1.
    Utilizes Numpy sliding window views to vectorize the returns and probability distribution.
    """
    try:
        period = int(options.get('period', 20))
        bins_count = int(options.get('bins', 10))
    except (ValueError, TypeError):
        period, bins_count = 20, 10

    n = len(df)
    entropy_arr = np.full(n, np.nan)
    efficiency_arr = np.full(n, np.nan)

    if n < period:
        return pl.DataFrame({
            "entropy": entropy_arr,
            "efficiency": efficiency_arr
        })

    close_v = df["close"].to_numpy()
    returns_v = np.diff(close_v) 
    
    ret_window_size = period - 1
    
    ret_windows = np.lib.stride_tricks.sliding_window_view(returns_v, window_shape=ret_window_size)
    
    max_entropy = np.log2(bins_count) if bins_count > 0 else 1.0

    for i, w_ret in enumerate(ret_windows):
        counts, _ = np.histogram(w_ret, bins=bins_count)
        
        probs = counts / ret_window_size
        probs = probs[probs > 0] # Shannon Entropy ignores zero probabilities
        
        entropy = -np.sum(probs * np.log2(probs))
        efficiency = 1.0 - (entropy / max_entropy) if max_entropy > 0 else 1.0
        
        idx = i + period - 1
        entropy_arr[idx] = entropy
        efficiency_arr[idx] = np.clip(efficiency, 0, 1)

    return pl.DataFrame({
        "entropy": entropy_arr,
        "efficiency": efficiency_arr
    }).with_columns([
        pl.col("entropy").round(4),
        pl.col("efficiency").round(4)
    ])