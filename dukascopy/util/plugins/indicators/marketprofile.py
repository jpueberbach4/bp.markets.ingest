import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any
from functools import partial

try:
    import numba
except ImportError:
    raise ImportError("Numba is required. Run 'pip install numba' OR 'pip install -r requirements.txt'")

from util.plugins.indicators.helpers.marketprofile_backend import _marketprofile_backend

def description() -> str:
    return "Rolling Market Profile (TPO): Calculates Time-based POC and Value Area over a moving window."

def meta() -> Dict:
    return {"author": "Google Gemini", "version": 2.0, "panel": 0, "verified": 1, "polars": 1}

def warmup_count(options: Dict[str, Any]) -> int:
    return int(options.get('period', 240))

def position_args(args: List[str]) -> Dict[str, Any]:
    return {"period": args[0] if len(args) > 0 else "240", "ticks": args[1] if len(args) > 1 else "1.0"}

def _mp_map_wrapper(s: pl.Series, period: int, tick_size: float) -> pl.Series:
    highs = s.struct.field("high").to_numpy()
    lows = s.struct.field("low").to_numpy()
    closes = s.struct.field("close").to_numpy()
    
    poc, vah, val = _marketprofile_backend(highs, lows, closes, period, tick_size)
    
    return pl.DataFrame({
        "poc": poc,
        "vah": vah,
        "val": val
    }).to_struct("mp_results")

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    p = int(options.get('period', 240))
    t = float(options.get('ticks', 1.0))

    mapper = partial(_mp_map_wrapper, period=p, tick_size=t)

    mp_schema = pl.Struct([
        pl.Field("poc", pl.Float64),
        pl.Field("vah", pl.Float64),
        pl.Field("val", pl.Float64),
    ])

    mp_base = (
        pl.struct(["high", "low", "close"])
        .map_batches(mapper, return_dtype=mp_schema)
    )

    return [
        mp_base.struct.field("poc").alias(f"{indicator_str}__poc"),
        mp_base.struct.field("vah").alias(f"{indicator_str}__vah"),
        mp_base.struct.field("val").alias(f"{indicator_str}__val"),
    ]