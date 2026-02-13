import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any
from functools import partial

try:
    import numba
except ImportError:
    raise ImportError("Numba is required. Run 'pip install numba' OR 'pip install -r requirements.txt'")

from util.plugins.indicators.helpers.linregchannel_backend import _linregchannel_backend

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "Linear Regression Channels use a mathematical 'best-fit' line to identify "
        "the center of a price trend. The indicator consists of three lines: the "
        "Median Line (a linear regression line), and Upper and Lower Channels based "
        "on the maximum price deviation from that line over a set period. It is "
        "highly effective for identifying trend exhaustion and potential price "
        "reversals when price touches the outer channel boundaries."
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
    Calculates the required warmup rows for Linear Regression Channels.
    """
    try:
        period = int(options.get('period', 50))
    except (ValueError, TypeError):
        period = 50
    return period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    """
    return {
        "period": args[0] if len(args) > 0 else "50"
    }

def _linregchannel_map_wrapper(s: pl.Series, period: int) -> pl.Series:
    y = s.to_numpy()
    mid, upper, lower = _linregchannel_backend(y, period)
    
    return pl.DataFrame({
        "lin_mid": mid,
        "lin_upper": upper,
        "lin_lower": lower
    }).to_struct("lrc_results")

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    p = int(options.get('period', 50))
    mapper = partial(_linregchannel_map_wrapper, period=p)

    lrc_schema = pl.Struct([
        pl.Field("lin_mid", pl.Float64),
        pl.Field("lin_upper", pl.Float64),
        pl.Field("lin_lower", pl.Float64),
    ])

    lrc_base = pl.col("close").map_batches(mapper, return_dtype=lrc_schema)

    return [
        lrc_base.struct.field("lin_mid").alias(f"{indicator_str}__mid"),
        lrc_base.struct.field("lin_upper").alias(f"{indicator_str}__upper"),
        lrc_base.struct.field("lin_lower").alias(f"{indicator_str}__lower")
    ]
