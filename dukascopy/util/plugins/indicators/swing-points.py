import polars as pl
import numpy as np
from typing import Dict, Any, List

def description() -> str:
    return (
        "Swing Points (Fractals): Identifies local Highs and Lows. "
        "Standard Williams Fractal = 2 Left, 2 Right. "
        "Useful for placing stops or identifying Market Structure Breaks (MSB)."
    )

def meta() -> Dict:
    return {
        "author": "Google Gemini",
        "version": 1.0,
        "panel": 0,           # Overlay
        "verified": 1,
        "polars": 0,
        "polars_input": 1
    }

def warmup_count(options: Dict[str, Any]) -> int:
    try:
        left = int(options.get('left', 2))
        right = int(options.get('right', 2))
        return left + right + 1
    except:
        return 5

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Args: left_strength, right_strength
    Example: 2,2 (Williams) or 5,5 (Major Swing)
    """
    return {
        "left": args[0] if len(args) > 0 else "2",
        "right": args[1] if len(args) > 1 else "2"
    }

def calculate(df: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    """
    Vectorized Swing Point detection using Numpy sliding windows.
    """
    try:
        left = int(options.get('left', 2))
        right = int(options.get('right', 2))
    except (ValueError, TypeError):
        left, right = 2, 2

    window_size = left + right + 1
    n = len(df)
    
    swing_highs = np.full(n, np.nan)
    swing_lows = np.full(n, np.nan)

    if n < window_size:
        return pl.DataFrame({
            "swing_high": swing_highs, 
            "swing_low": swing_lows
        })

    highs = df['high'].to_numpy()
    lows = df['low'].to_numpy()

    high_windows = np.lib.stride_tricks.sliding_window_view(highs, window_shape=window_size)
    low_windows = np.lib.stride_tricks.sliding_window_view(lows, window_shape=window_size)

    center_idx = left  # e.g., index 2 in a size 5 window
        
    center_highs = high_windows[:, center_idx]
    center_lows = low_windows[:, center_idx]
    
    window_max = np.max(high_windows, axis=1)
    window_min = np.min(low_windows, axis=1)
    
    is_swing_high = (center_highs == window_max)
    is_swing_low = (center_lows == window_min)
    
    high_indices = np.where(is_swing_high)[0]
    low_indices = np.where(is_swing_low)[0]
    
    swing_highs[high_indices + center_idx] = center_highs[high_indices]
    swing_lows[low_indices + center_idx] = center_lows[low_indices]

    return pl.DataFrame({
        "swing_high": swing_highs,
        "swing_low": swing_lows
    })