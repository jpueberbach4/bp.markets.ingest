import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    """
    The McGinley Dynamic is a smoothing mechanism that minimizes lag and 
    avoids whipsaws by adjusting its speed based on the market's velocity.
    Formula: MD[i] = MD[i-1] + (Price[i] - MD[i-1]) / (N * (Price[i] / MD[i-1])^4)
    """
    return "McGinley Dynamic: An adaptive moving average that adjusts tracking speed based on volatility."

def meta() -> Dict:
    return {
        "author": "Google Gemini",
        "version": 1.1,
        "panel": 0,
        "verified": 1,
        "polars": 1 # Now actually implemented
    }

def warmup_count(options: Dict[str, Any]) -> int:
    return int(options.get('period', 14)) * 2

def position_args(args: List[str]) -> Dict[str, Any]:
    return {"period": args[0] if len(args) > 0 else "14"}

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    p = int(options.get('period', 14))
    
    def apply_mcginley(s: pl.Series) -> pl.Series:
        prices = s.to_numpy()
        n = len(prices)
        md = np.zeros(n)
        
        md[0] = prices[0]
        
        for i in range(1, n):
            prev_md = md[i-1]
            price = prices[i]
            
            if prev_md == 0:
                md[i] = price
                continue
                
            ratio = price / prev_md
            denominator = p * (ratio ** 4)
            
            md[i] = prev_md + (price - prev_md) / denominator
            
        return pl.Series(md)

    return [
        pl.col("close").map_batches(apply_mcginley).alias(f"{indicator_str}__value")
    ]

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    p = int(options.get('period', 14))
    
    close = df['close'].values
    n = len(close)
    md = np.zeros(n)
    
    md[0] = close[0]
    
    for i in range(1, n):
        prev_md = md[i-1]
        price = close[i]
        
        if prev_md == 0:
            md[i] = price
            continue
            
        ratio = price / prev_md
        denominator = p * (ratio ** 4)
        
        md[i] = prev_md + (price - prev_md) / denominator
        
    return pd.DataFrame({'value': md}, index=df.index)