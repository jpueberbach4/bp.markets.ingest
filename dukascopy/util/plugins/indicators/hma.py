import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any, Union

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "The Hull Moving Average (HMA) is an extremely fast and smooth moving average "
        "designed to almost eliminate lag while simultaneously improving smoothing. "
        "Formula: WMA(2*WMA(n/2) - WMA(n), sqrt(n))"
    )

def meta() -> Dict:
    return {
        "author": "Google Gemini",
        "version": 1.1,
        "verified": 0,  # Needs fixing!
        "polars": 1     # TODO: fix polars version. performance profile if polars version is faster 
                        # since uses UDF function. For now, fallback to pandas version. 
    }

def warmup_count(options: Dict[str, Any]) -> int:
    try:
        period = int(options.get('period', 9))
    except (ValueError, TypeError):
        period = 9
    return period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    return {"period": args[0] if len(args) > 0 else "9"}

def _polars_wma(column: Union[str, pl.Expr], n: int) -> pl.Expr:
    """
    Calculates Weighted Moving Average (WMA) using Vectorized Double-Cumsum.
    
    Algorithm:
        Target WMA (Step-Up weights n, n-1, ... 1) can be derived from two cumulative sums.
        Formula: Numerator = (n+1)*S1_t - S1_{t-n} - (S2_t - S2_{t-n})
        Where:
            S1 = Cumulative Sum of Price
            S2 = Cumulative Sum of S1
            
    Performance:
        Removes the O(N*W) complexity of rolling_map.
        Executes in pure Rust/SIMD.
    """
    # Normalize input to Expression
    col = pl.col(column) if isinstance(column, str) else column
    
    # 1. Prepare Cumulative Sums
    # fill_null(0) is required to allow the math to start from index 0
    # The result for the warmup period will be junk, but masked later by null propagation
    s1 = col.fill_null(0).cum_sum()
    s2 = s1.cum_sum()
    
    # 2. Calculate Window Terms
    # s1_shifted represents S1_{t-n}
    s1_shift = s1.shift(n).fill_null(0)
    s2_shift = s2.shift(n).fill_null(0)
    
    # 3. Vectorized WMA Formula
    # Derivation: (n+1) * FlatSum - StepDownSum = StepUpSum
    numerator = (n + 1) * s1 - s1_shift - (s2 - s2_shift)
    denominator = n * (n + 1) // 2
    
    # 4. Mask warmup period
    # The shift operation naturally creates nulls at the start, but fill_null(0) 
    # hid them. We re-apply nulls to the first n-1 elements to be safe.
    wma = numerator / denominator
    
    # Helper to enforce nulls on the warmup period (first n-1 rows)
    return wma.shift(- (n - 1)).shift(n - 1)

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> pl.Expr:
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14

    half_p = int(period / 2)
    sqrt_p = int(np.sqrt(period))

    # Calculate WMA components using the vectorized helper
    wma_half = _polars_wma("close", half_p)
    wma_full = _polars_wma("close", period)
    
    # Raw Hull Moving Average
    # Formula: 2 * WMA(n/2) - WMA(n)
    raw_hma = (wma_half * 2) - wma_full
    
    # Final Smoothing: WMA(sqrt(n))
    return _polars_wma(raw_hma, sqrt_p).alias(indicator_str)

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    Legacy Pandas fallback using the optimized NumPy logic.
    """
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14

    def fast_wma(series, n):
        if n < 1: return series
        weights = np.arange(1, n + 1)
        # Simplified rolling window for fallback compatibility
        return series.rolling(window=n).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True)

    half_period = int(period / 2)
    sqrt_period = int(np.sqrt(period))

    wma_half = fast_wma(df['close'], half_period)
    wma_full = fast_wma(df['close'], period)
    raw_hma = (2 * wma_half) - wma_full
    hma = fast_wma(raw_hma, sqrt_period)

    return pd.DataFrame({'hma': hma}, index=df.index).dropna()