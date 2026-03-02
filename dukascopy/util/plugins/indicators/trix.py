import polars as pl
import numpy as np
from typing import List, Dict, Any

try:
    import numba
except ImportError:
    raise ImportError("Numba is required. Run 'pip install numba' OR 'pip install -r requirements.txt'")

from util.plugins.indicators.helpers.trix_backend import _trix_backend

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "The TRIX indicator (Triple Exponential Average) is a momentum oscillator "
        "used to identify oversold and overbought markets. It filters out market "
        "noise by applying a triple exponential moving average to the closing price, "
        "and then calculating the percentage rate of change."
    )

def meta() -> Dict:
    """
    Metadata for the dual-engine orchestrator.
    """
    return {
        "author": "Google Gemini",
        "version": 1.0, 
        "panel": 1,
        "verified": 1,
        "polars": 1
    }

def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for the TRIX Indicator.
    Requires 3 sequential EMA passes, taking 3 * period to fully stabilize.
    """
    try:
        period = int(options.get('period', 15))
    except (ValueError, TypeError):
        period = 15
    return 3 * period

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    """
    return {
        "period": args[0] if len(args) > 0 else "15"
    }

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    p = int(options.get('period', 15))

    trix = pl.col("close").map_batches(
        lambda s: _trix_backend(s.to_numpy(), p), 
        return_dtype=pl.Float64
    )

    return [
        trix.alias(f"{indicator_str}"),
    ]