import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any
from functools import partial

try:
    import numba
except ImportError:
    raise ImportError("Numba is required. Run 'pip install numba' OR 'pip install -r requirements.txt'")

from util.plugins.indicators.helpers.stc_backend import _stc_backend

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "The Schaff Trend Cycle (STC) is a high-speed oscillator that combines the "
        "benefits of MACD and slow Stochastics. By applying a double-smoothed "
        "stochastic process to MACD values, it identifies market trends and "
        "cyclical turns much faster than traditional indicators. It is designed "
        "to stay at extreme levels (0 or 100) during strong trends and provide "
        "early warnings of trend exhaustion through its rapid 'cycle' movement."
    )

def meta() -> Dict:
    """
    Metadata for the dual-engine orchestrator.
    """
    return {
        "author": "Google Gemini",
        "version": 1.2,
        "panel": 1,
        "verified": 1,
        "polars": 1
    }

def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for the Schaff Trend Cycle.
    """
    try:
        slow = int(options.get('slow', 50))
    except (ValueError, TypeError):
        slow = 50
    return slow * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: stc_10_23_50 -> {'cycle': '10', 'fast': '23', 'slow': '50'}
    """
    return {
        "cycle": args[0] if len(args) > 0 else "10",
        "fast": args[1] if len(args) > 1 else "23",
        "slow": args[2] if len(args) > 2 else "50"
    }

def _stc_map_wrapper(s: pl.Series, cycle: int, fast: int, slow: int) -> pl.Series:
    close_v = s.to_numpy()
    stc_values = _stc_backend(close_v, cycle, fast, slow)
    
    direction = np.where(stc_values > np.roll(stc_values, 1), 1, -1).astype(np.int32)
    direction[0] = 0 # Handle initial roll
    
    return pl.DataFrame({
        "stc": stc_values,
        "direction": direction
    }).to_struct("stc_results")

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    c = int(options.get('cycle', 10))
    f = int(options.get('fast', 23))
    s = int(options.get('slow', 50))

    mapper = partial(_stc_map_wrapper, cycle=c, fast=f, slow=s)

    stc_schema = pl.Struct([
        pl.Field("stc", pl.Float64),
        pl.Field("direction", pl.Int32),
    ])

    stc_base = pl.col("close").map_batches(mapper, return_dtype=stc_schema)

    return [
        stc_base.struct.field("stc").alias(f"{indicator_str}__stc"),
        stc_base.struct.field("direction").alias(f"{indicator_str}__direction")
    ]
