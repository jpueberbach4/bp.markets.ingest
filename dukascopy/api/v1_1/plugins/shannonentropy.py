import pandas as pd
import numpy as np
from typing import List, Dict, Any

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: shannonentropy_20_10 -> {'period': '20', 'bins': '10'}
    """
    return {
        "period": args[0] if len(args) > 0 else "20",
        "bins": args[1] if len(args) > 1 else "10"
    }

def get_entropy_stats(y: np.ndarray, bins: int):
    """
    Calculates Shannon Entropy and Efficiency for a price segment.
    """
    # Create a histogram of price returns to find the distribution
    # We use returns (diff) rather than raw price for stationarity
    returns = np.diff(y)
    if len(returns) == 0:
        return 0.0, 1.0
        
    counts, _ = np.histogram(returns, bins=bins)
    probs = counts / np.sum(counts)
    probs = probs[probs > 0] # Filter out zero-probability bins
    
    # Shannon Entropy Formula: -Sum(p * log2(p))
    entropy = -np.sum(probs * np.log2(probs))
    
    # Efficiency: 1 - (Actual Entropy / Max Possible Entropy)
    max_entropy = np.log2(bins)
    efficiency = 1.0 - (entropy / max_entropy) if max_entropy > 0 else 1.0
    
    return entropy, np.clip(efficiency, 0, 1)

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    High-performance vectorized Shannon Entropy calculation.
    """
    # 1. Parse Parameters
    try:
        period = int(options.get('period', 20))
        bins = int(options.get('bins', 10))
    except (ValueError, TypeError):
        period, bins = 20, 10

    # 2. Calculation Logic
    # Using rolling.apply with raw=True for NumPy speed
    # We return entropy first, then efficiency in a separate pass
    entropy_raw = df['close'].rolling(window=period).apply(
        lambda x: get_entropy_stats(x, bins)[0], raw=True
    )
    
    efficiency_raw = df['close'].rolling(window=period).apply(
        lambda x: get_entropy_stats(x, bins)[1], raw=True
    )

    # 3. Final Formatting and Rounding
    # Preserving the original index for O(1) merging in parallel.py
    res = pd.DataFrame({
        'entropy': entropy_raw.round(4),
        'efficiency': efficiency_raw.round(4)
    }, index=df.index)
    
    # Drop rows where the window hasn't filled (warm-up period)
    return res.dropna(subset=['entropy'])