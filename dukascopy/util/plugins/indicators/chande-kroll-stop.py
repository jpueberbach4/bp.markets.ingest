import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    return "Chande Kroll Stop is a trend-following stop-loss indicator that identifies exits based on volatility."

def meta() -> Dict:
    return {"author": "Google Gemini", "version": 1.0, "panel": 0, "verified": 1, "polars": 1}

def warmup_count(options: Dict[str, Any]) -> int:
    p = int(options.get('period', 10))
    x = int(options.get('multiplier', 1))
    return p + x

def position_args(args: List[str]) -> Dict[str, Any]:
    return {"period": args[0] if len(args) > 0 else "10", "multiplier": args[1] if len(args) > 1 else "1"}

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    p = int(options.get('period', 10))
    m = float(options.get('multiplier', 1.0))
    
    tr = pl.max_horizontal([(pl.col("high") - pl.col("low")), (pl.col("high") - pl.col("close").shift(1)).abs()])
    atr = tr.rolling_mean(window_size=p)
    
    # Preliminary stops
    high_stop = pl.col("high").rolling_max(window_size=p) - (m * atr)
    low_stop = pl.col("low").rolling_min(window_size=p) + (m * atr)
    
    return [
        high_stop.rolling_max(window_size=p).alias(f"{indicator_str}__stop_short"),
        low_stop.rolling_min(window_size=p).alias(f"{indicator_str}__stop_long")
    ]