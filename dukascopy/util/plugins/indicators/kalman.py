import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    return "The Kalman Filter is a recursive filter that tracks the 'true' state of price by filtering out noise."

def meta() -> Dict:
    return {
        "author": "Google Gemini",
        "version": 1.1,
        "panel": 0,
        "verified": 1,
        "polars": 1
    }

def warmup_count(options: Dict[str, Any]) -> int:
    return 1

def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "q": args[0] if len(args) > 0 else "1e-5",
        "r": args[1] if len(args) > 1 else "0.01"
    }

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    """
    Polars implementation using a series-based map for the recursive state.
    """
    q_val = float(options.get('q', 1e-5))
    r_val = float(options.get('r', 0.01))

    def apply_kalman(s: pl.Series) -> pl.Series:
        values = s.to_numpy()
        size = len(values)
        xhat = np.zeros(size)
        P = np.zeros(size)
        
        xhat[0] = values[0]
        P[0] = 1.0
        
        for k in range(1, size):
            p_minus = P[k-1] + q_val
            k_gain = p_minus / (p_minus + r_val)
            xhat[k] = xhat[k-1] + k_gain * (values[k] - xhat[k-1])
            P[k] = (1 - k_gain) * p_minus
            
        return pl.Series(xhat)

    return [
        pl.col("close").map_batches(apply_kalman).alias(f"{indicator_str}__kalman")
    ]

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """Legacy Pandas fallback."""
    q_val = float(options.get('q', 1e-5))
    r_val = float(options.get('r', 0.01))
    
    close = df['close'].values
    size = len(close)
    xhat = np.zeros(size)
    P = np.zeros(size)
    
    xhat[0] = close[0]
    P[0] = 1.0

    for k in range(1, size):
        p_minus = P[k-1] + q_val
        k_gain = p_minus / (p_minus + r_val)
        xhat[k] = xhat[k-1] + k_gain * (close[k] - xhat[k-1])
        P[k] = (1 - k_gain) * p_minus

    return pd.DataFrame({'kalman': xhat}, index=df.index)