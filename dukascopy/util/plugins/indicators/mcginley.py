import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any
from functools import partial

try:
    import numba
except ImportError:
    raise ImportError("Numba is required. Run 'pip install numba' OR 'pip install -r requirements.txt'")

from util.plugins.indicators.helpers.mcginley_backend import _mcginley_backend

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
        "polars": 1
    }

def warmup_count(options: Dict[str, Any]) -> int:
    return int(options.get('period', 14)) * 2

def position_args(args: List[str]) -> Dict[str, Any]:
    return {"period": args[0] if len(args) > 0 else "14"}

def _mcginley_map_wrapper(s: pl.Series, p: int) -> pl.Series:
    prices = s.to_numpy()
    result = _mcginley_backend(prices, p)
    return pl.Series(result)

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    try:
        p = int(options.get('period', 14))
    except (ValueError, TypeError):
        p = 14

    mapper = partial(_mcginley_map_wrapper, p=p)

    return [
        pl.col("close")
        .map_batches(mapper, return_dtype=pl.Float64)
        .alias(f"{indicator_str}__value")
    ]
