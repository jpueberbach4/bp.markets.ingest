import pandas as pd
import numpy as np
import polars as pl
from functools import partial
from typing import List, Dict, Any

try:
    import numba
except ImportError:
    raise ImportError("Numba is required. Run 'pip install numba' OR 'pip install -r requirements.txt'")

from util.plugins.indicators.helpers.supertrend_backend import _supertrend_backend

def description() -> str:
    return "SuperTrend is a trend-following indicator based on ATR. It provides a clear floor (uptrend) or ceiling (downtrend) for price action."

def meta() -> Dict:
    return {"author": "Google Gemini", "version": 2.1, "panel": 0, "verified": 1, "polars": 1}

def warmup_count(options: Dict[str, Any]) -> int:
    return int(options.get('period', 10)) * 2

def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "period": args[0] if len(args) > 0 else "10",
        "multiplier": args[1] if len(args) > 1 else "3.0"
    }

def _supertrend_map_wrapper(s: pl.Series, period: int, multiplier: float) -> pl.Series:
    high = s.struct.field("high").to_numpy()
    low = s.struct.field("low").to_numpy()
    close = s.struct.field("close").to_numpy()
    
    result = _supertrend_backend(high, low, close, period, multiplier)
    
    return pl.Series(result)

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    p = int(options.get('period', 10))
    m = float(options.get('multiplier', 3.0))

    mapper = partial(_supertrend_map_wrapper, period=p, multiplier=m)

    return [
        pl.struct(["high", "low", "close"])
        .map_batches(mapper)
        .alias(f"{indicator_str}__value")
    ]
