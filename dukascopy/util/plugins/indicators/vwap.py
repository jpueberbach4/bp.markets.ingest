import polars as pl
import pandas as pd
import numpy as np
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "VWAP (Volume Weighted Average Price) is a technical analysis indicator "
        "used to measure the average price an asset has traded at throughout the "
        "day, based on both volume and price. It provides traders with insight "
        "into both the trend and value of an asset. VWAP is often used as a "
        "benchmark by institutional traders to ensure they are executing orders "
        "close to the market average, rather than pushing the price away from "
        "its established value."
    )

def meta() -> Dict:
    """
    Metadata for the dual-engine orchestrator.
    """
    return {
        "author": "Google Gemini",
        "version": 1.1,
        "verified": 1,
        "polars": 1
    }

def warmup_count(options: Dict[str, Any]) -> int:
    """
    VWAP requires a calculation from the session start. 
    500 bars is a safe default for intraday high-frequency data.
    """
    return 500

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    VWAP typically takes no additional positional parameters.
    """
    return {}

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> pl.Expr:
    vol = pl.col("volume").cast(pl.Float64)
    # Multiplication is faster on CPU
    tp = (pl.col("high") + pl.col("low") + pl.col("close")) * 0.3333333333333333
    return (
        (tp * vol).cum_sum().over(pl.col("time_ms") // 86400000) 
        / 
        vol.cum_sum().over(pl.col("time_ms") // 86400000)
    ).alias(indicator_str)