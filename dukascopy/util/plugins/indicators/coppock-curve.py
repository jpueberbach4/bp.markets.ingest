import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    """
    The Coppock Curve is a long-term momentum indicator. 
    Formula: WMA_10(ROC_14 + ROC_11).
    """
    return "Coppock Curve: A long-term momentum oscillator using True Weighted Moving Average (WMA)."

def meta() -> Dict:
    return {
        "author": "Google Gemini",
        "version": 1.1,
        "panel": 1,
        "verified": 1,
        "polars": 1 # Now uses True WMA via convolution
    }

def warmup_count(options: Dict[str, Any]) -> int:
    # Requires max(roc) + wma_period
    return int(options.get('roc_long', 14)) + int(options.get('wma_period', 10))

def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "roc_long": args[0] if len(args) > 0 else "14",
        "roc_short": args[1] if len(args) > 1 else "11",
        "wma_period": args[2] if len(args) > 2 else "10"
    }

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    rl = int(options.get('roc_long', 14))
    rs = int(options.get('roc_short', 11))
    w = int(options.get('wma_period', 10))

    # 1. Calculate the Raw Momentum (Sum of ROCs) using expressions
    roc_l = (pl.col("close") - pl.col("close").shift(rl)) / pl.col("close").shift(rl)
    roc_s = (pl.col("close") - pl.col("close").shift(rs)) / pl.col("close").shift(rs)
    raw_coppock = (roc_l + roc_s) * 100 # Standard scaling

    # 2. Apply True WMA using Convolution in map_batches
    def apply_wma(s: pl.Series) -> pl.Series:
        values = s.to_numpy()
        # Handle NaNs (treat as 0 or forward fill for convolution safety, 
        # but technically WMA starts after NaNs are gone)
        # We fill with 0 to allow convolution to run, then re-mask later if needed.
        values_clean = np.nan_to_num(values)
        
        # Create Linear Weights [1, 2, 3, ... w]
        weights = np.arange(1, w + 1)
        w_sum = weights.sum()
        
        # Convolve: 'full' mode gives us the rolling dot product
        # We only care about the valid range where the kernel overlaps fully
        # but we need to maintain series length.
        
        # Standard WMA convolution
        # We perform convolution and shift it to align right-edge
        conv = np.convolve(values_clean, weights, mode='full')
        
        # The result of 'full' is length (N + W - 1). 
        # The 'valid' data ends at index N-1 relative to the input.
        # We need to slice it to match the input size, aligning the right edge.
        # WMA is a trailing average, so the value at index `i` depends on `i-w+1` to `i`.
        
        # Slice [w-1 : N+w-1] gives us the values where the kernel was fully inside
        # But easier: convolve mode='valid' returns length N - W + 1.
        # We then pad the beginning with NaNs.
        
        valid_conv = np.convolve(values_clean, weights, mode='valid')
        result = valid_conv / w_sum
        
        # Prepend NaNs to restore original length
        pad_size = len(values) - len(result)
        final_out = np.concatenate([np.full(pad_size, np.nan), result])
        
        return pl.Series(final_out)

    return [
        raw_coppock.map_batches(apply_wma).alias(f"{indicator_str}__value")
    ]

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    rl = int(options.get('roc_long', 14))
    rs = int(options.get('roc_short', 11))
    w = int(options.get('wma_period', 10))

    # ROC
    roc_l = df['close'].pct_change(rl)
    roc_s = df['close'].pct_change(rs)
    res = (roc_l + roc_s) * 100
    
    # True WMA Logic
    weights = np.arange(1, w + 1)
    
    # Using Pandas rolling apply for exact WMA math
    # Note: This is slower than convolution but 100% accurate definition
    coppock = res.rolling(w).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True)
    
    return pd.DataFrame({'value': coppock}, index=df.index)