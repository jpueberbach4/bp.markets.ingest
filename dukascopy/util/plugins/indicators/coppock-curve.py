import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    """
    The Coppock Curve is a long-term price momentum indicator used to identify 
    major bottoms in the stock market. It is calculated as a 10-period weighted 
    moving average of the sum of a 14-period ROC and an 11-period ROC.
    """
    return "Coppock Curve: A long-term momentum indicator for identifying major trend reversals."

def meta() -> Dict:
    return {
        "author": "Google Gemini",
        "version": 1.0,
        "panel": 1,
        "verified": 1,
        "polars": 1
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

    # Calculate ROCs
    roc_l = (pl.col("close") - pl.col("close").shift(rl)) / pl.col("close").shift(rl)
    roc_s = (pl.col("close") - pl.col("close").shift(rs)) / pl.col("close").shift(rs)
    
    # Combined Momentum
    res = roc_l + roc_s
    
    # Smooth using EWM as a high-speed proxy for WMA in Polars
    coppock = res.ewm_mean(span=w, adjust=False)
    
    return [coppock.alias(f"{indicator_str}__value")]

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    rl = int(options.get('roc_long', 14))
    rs = int(options.get('roc_short', 11))
    w = int(options.get('wma_period', 10))

    roc_l = df['close'].pct_change(rl)
    roc_s = df['close'].pct_change(rs)
    res = roc_l + roc_s
    
    # Standard WMA smoothing for Pandas fallback
    weights = np.arange(1, w + 1)
    coppock = res.rolling(w).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True)
    
    return pd.DataFrame({'value': coppock}, index=df.index).dropna()