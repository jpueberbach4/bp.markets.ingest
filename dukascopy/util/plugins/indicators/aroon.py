import polars as pl
from typing import List, Dict, Any
from functools import partial

try:
    import numba
except ImportError:
    raise ImportError("Numba is required. Run 'pip install numba' OR 'pip install -r requirements.txt'")

from util.plugins.indicators.helpers.aroon_backend import _aroon_backend_down, _aroon_backend_up



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

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    p = int(options.get('period', 14))

    aroon_up = pl.col("high").map_batches(
        lambda s: _aroon_backend_up(s.to_numpy(), p), 
        return_dtype=pl.Float64
    )
    
    aroon_down = pl.col("low").map_batches(
        lambda s: _aroon_backend_down(s.to_numpy(), p), 
        return_dtype=pl.Float64
    )

    return [
        aroon_up.alias(f"{indicator_str}__up"),
        aroon_down.alias(f"{indicator_str}__down"),
    ]
