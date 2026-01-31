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
        "polars": 0     # TODO: fix polars version. performance profile if polars version is faster 
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
    # Ensure we are working with an Expression
    if isinstance(column, str):
        col_expr = pl.col(column)
    else:
        col_expr = column
        
    weights = list(range(1, n + 1))
    sum_weights = sum(weights)
    
    # Use rolling_map with a closure to handle weights
    return col_expr.rolling_map(
        lambda s: (s * weights).sum() / sum_weights,
        window_size=n
    )

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> pl.Expr:
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14

    half_p = period // 2
    sqrt_p = int(np.sqrt(period))

    # Calculate WMA components
    # 2 * WMA(n/2) - WMA(n)
    wma_half = _polars_wma("close", half_p)
    wma_full = _polars_wma("close", period)
    
    diff_expr = (wma_half * 2) - wma_full
    
    # Final HMA smoothing
    return _polars_wma(diff_expr, sqrt_p).alias(indicator_str)

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