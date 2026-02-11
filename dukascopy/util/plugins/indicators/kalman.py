import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any
from functools import partial

try:
    import numba
except ImportError:
    raise ImportError("Numba is required. Run 'pip install numba' OR 'pip install -r requirements.txt'")

from util.plugins.indicators.helpers.kalman_backend import _kalman_backend


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

def _kalman_map_wrapper(s: pl.Series, q: float, r: float) -> pl.Series:
    values = s.to_numpy()
    result = _kalman_backend(values, q, r)
    return pl.Series(result)

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    try:
        q_val = float(options.get('q', 1e-5))
        r_val = float(options.get('r', 0.01))
    except (ValueError, TypeError):
        q_val, r_val = 1e-5, 0.01

    mapper = partial(_kalman_map_wrapper, q=q_val, r=r_val)

    return [
        pl.col("close")
        .map_batches(mapper, return_dtype=pl.Float64)
        .alias(f"{indicator_str}__kalman")
    ]