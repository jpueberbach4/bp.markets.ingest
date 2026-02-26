import polars as pl
import pandas as pd
import numpy as np
from typing import List, Dict, Any

def description() -> str:
    return (
        "VWAP Percentage Deviation measures how far the current price is from the "
        "Volume Weighted Average Price as a percentage. This stationary version "
        "is asset-agnostic and transferable across different price scales."
    )

def meta() -> Dict:
    return {
        "author": "Google Gemini",
        "version": 1.2,
        "verified": 1,
        "polars": 1,
        "panel": 1
    }

def warmup_count(options: Dict[str, Any]) -> int:
    # 500 bars provides a stable cumulative baseline for intraday/4h data
    return 500

def position_args(args: List[str]) -> Dict[str, Any]:
    return {}

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> pl.Expr:
    vol = pl.col("volume").cast(pl.Float64)
    tp = (pl.col("high") + pl.col("low") + pl.col("close")) * 0.3333333333333333
    
    # Calculate absolute VWAP (Cumulative by day/session)
    vwap_abs = (
        (tp * vol).cum_sum().over(pl.col("time_ms") // 86400000) 
        / 
        vol.cum_sum().over(pl.col("time_ms") // 86400000)
    )
    
    # TRANSFORM: Convert to percentage deviation for transferability
    # Formula: (Price - VWAP) / VWAP
    vwap_pct = (pl.col("close") - vwap_abs) / vwap_abs
    
    return vwap_pct.alias(indicator_str)
