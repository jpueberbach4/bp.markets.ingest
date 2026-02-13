import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any
from functools import partial

try:
    import numba
except ImportError:
    raise ImportError("Numba is required. Run 'pip install numba' OR 'pip install -r requirements.txt'")

from util.plugins.indicators.helpers.zigzag_backend import _zigzag_backend



def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "ZigZag identifies significant turning points (peaks and troughs) "
        "that deviate from the previous swing by a specified percentage. "
        "It filters out noise to visualize the underlying trend structure."
        "Use 0.5 for forex and >1.0 for stocks."
    )

def meta() -> Dict:
    """
    Metadata for the dual-engine orchestrator.
    """
    return {
        "author": "Google Gemini",
        "version": 1.1,
        "panel": 0,
        "verified": 1,
        "talib-validated": 0,
        "polars": 1
    }

def warmup_count(options: Dict[str, Any]) -> int:
    """
    ZigZag needs enough history to find at least one valid swing.
    """
    return 100

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    """
    return {
        "deviation": args[0] if len(args) > 0 else "0.5"
    }

def _map_wrapper(s: pl.Series, dev_threshold: float) -> pl.Series:
    highs = s.struct.field("high").to_numpy()
    lows = s.struct.field("low").to_numpy()
    
    pivots = _zigzag_backend(highs, lows, dev_threshold)
    return pl.Series(pivots)

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    try:
        deviation = float(options.get('deviation', 5.0))
    except (ValueError, TypeError):
        deviation = 5.0

    dev_threshold = deviation / 100.0
    mapper = partial(_map_wrapper, dev_threshold=dev_threshold)

    return [
        pl.struct(["high", "low"])
        .map_batches(mapper, return_dtype=pl.Float64)
        .interpolate()
        .alias(f"{indicator_str}__value")
    ]