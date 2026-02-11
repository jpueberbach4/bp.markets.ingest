import polars as pl
from typing import List, Dict, Any
from functools import partial

try:
    import numba
except ImportError:
    raise ImportError("Numba is required. Run 'pip install numba' OR 'pip install -r requirements.txt'")

from util.plugins.indicators.helpers.aroon_backend import _aroon_backend



def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "The Aroon Indicator identifies whether an asset is trending and the "
        "strength of that trend. It consists of 'Aroon Down' (measuring time "
        "since lowest low) and 'Aroon Up' (measuring time since highest high)."
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
        "talib-validated": 1, 
        "polars": 1
    }

def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for the Aroon Indicator.
    """
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14
    return period + 1

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    """
    return {
        "period": args[0] if len(args) > 0 else "14"
    }


def _aroon_map_wrapper(s: pl.Series, period: int) -> pl.Series:
    """
    Wrapper to bridge Polars Series and Numba backend.
    """
    highs = s.struct.field("high").to_numpy()
    lows = s.struct.field("low").to_numpy()
    
    aroon_up, aroon_down = _aroon_backend(highs, lows, period)
    
    return pl.DataFrame({
        "aroon_up": aroon_up,
        "aroon_down": aroon_down
    }).to_struct("aroon_results")

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    """
    High-performance Aroon using Numba + Polars map_batches.
    """
    try:
        p = int(options.get('period', 14))
    except (ValueError, TypeError):
        p = 14

    mapper = partial(_aroon_map_wrapper, period=p)

    aroon_schema = pl.Struct([
        pl.Field("aroon_up", pl.Float64),
        pl.Field("aroon_down", pl.Float64),
    ])

    aroon_base = (
        pl.struct(["high", "low"])
        .map_batches(mapper, return_dtype=aroon_schema)
    )

    return [
        aroon_base.struct.field("aroon_down").alias(f"{indicator_str}__aroon_down"),
        aroon_base.struct.field("aroon_up").alias(f"{indicator_str}__aroon_up")
    ]
