import polars as pl
import numpy as np
from typing import List, Dict, Any

try:
    import numba
except ImportError:
    raise ImportError("Numba is required. Run 'pip install numba' OR 'pip install -r requirements.txt'")

from util.plugins.indicators.helpers.mom_backend import _mom_backend

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "The Classic Momentum (MOM) indicator measures the amount that a security's price "
        "has changed over a given time span. It is calculated by subtracting the closing price "
        "of 'N' periods ago from the current closing price. It is used to identify trend strength "
        "and potential reversal points."
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
        "talib-validated": 1, 
        "polars": 1
    }

def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for the MOM Indicator.
    Requires exactly 'period' rows to look back.
    """
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14
    return period

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    """
    return {
        "period": args[0] if len(args) > 0 else "14"
    }

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    p = int(options.get('period', 14))

    mom = pl.col("close").map_batches(
        lambda s: _mom_backend(s.to_numpy(), p), 
        return_dtype=pl.Float64
    )

    return [
        mom.alias(f"{indicator_str}"),
    ]