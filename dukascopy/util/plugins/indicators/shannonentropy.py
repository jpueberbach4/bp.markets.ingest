import numpy as np
import polars as pl
from typing import List, Dict, Any
from functools import partial

try:
    import numba
except ImportError:
    raise ImportError("Numba is required. Run 'pip install numba' OR 'pip install -r requirements.txt'")

from util.plugins.indicators.helpers.shannonentropy_backend import _shannonentropy_backend

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "Shannon Entropy measures the complexity and unpredictability of price "
        "movements by analyzing the distribution of price returns. A higher entropy "
        "value suggests a more chaotic or random market state (high uncertainty), "
        "while lower values indicate more ordered, predictable patterns. The 'Efficiency' "
        "metric normalizes this value between 0 and 1, where 1 represents a perfectly "
        "ordered state and 0 represents maximum market chaos."
    )

def meta() -> Dict:
    """
    Metadata for the dual-engine orchestrator.
    """
    return {
        "author": "Google Gemini",
        "version": 1.3,
        "panel": 1,
        "verified": 1,
        "polars": 1
    }

def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for Shannon Entropy.
    """
    try:
        period = int(options.get('period', 20))
    except (ValueError, TypeError):
        period = 20
    return period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: shannonentropy_20_10 -> {'period': '20', 'bins': '10'}
    """
    return {
        "period": args[0] if len(args) > 0 else "20",
        "bins": args[1] if len(args) > 1 else "10"
    }

def _entropy_map_wrapper(s: pl.Series, period: int, bins: int) -> pl.Series:
    close_v = s.to_numpy()
    
    ent, eff = _shannonentropy_backend(close_v, period, bins)
    
    return pl.DataFrame({
        "entropy": ent,
        "efficiency": eff
    }).to_struct("entropy_results")

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    p = int(options.get('period', 20))
    b = int(options.get('bins', 10))

    mapper = partial(_entropy_map_wrapper, period=p, bins=b)

    entropy_schema = pl.Struct([
        pl.Field("entropy", pl.Float64),
        pl.Field("efficiency", pl.Float64),
    ])

    base = pl.col("close").map_batches(mapper, return_dtype=entropy_schema)

    return [
        base.struct.field("entropy").round(4).alias(f"{indicator_str}__entropy"),
        base.struct.field("efficiency").round(4).alias(f"{indicator_str}__efficiency"),
    ]
