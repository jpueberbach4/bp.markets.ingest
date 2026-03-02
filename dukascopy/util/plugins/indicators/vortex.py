import polars as pl
import numpy as np
from typing import List, Dict, Any

try:
    import numba
except ImportError:
    raise ImportError("Numba is required. Run 'pip install numba' OR 'pip install -r requirements.txt'")

from util.plugins.indicators.helpers.vortex_backend import _vortex_backend

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "The Vortex Indicator (VI) consists of two lines (+VI and -VI) that capture positive "
        "and negative trend movements. It is used to identify the start of a new trend or the "
        "continuation of an existing one by measuring the distance between the current high/low "
        "and the previous low/high."
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
        "talib-validated": 0, # TA-Lib doesn't natively support Vortex 
        "polars": 1
    }

def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for the Vortex Indicator.
    Requires 1 bar for initial High/Low diffs, plus the period for the sum.
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

    # We pack High, Low, and Close into a struct so the lambda can pass all three to Numba
    vortex_plus = pl.struct(["high", "low", "close"]).map_batches(
        lambda s: _vortex_backend(
            s.struct.field("high").to_numpy(),
            s.struct.field("low").to_numpy(),
            s.struct.field("close").to_numpy(),
            p,
            True # return_plus = True
        ), 
        return_dtype=pl.Float64
    )
    
    vortex_minus = pl.struct(["high", "low", "close"]).map_batches(
        lambda s: _vortex_backend(
            s.struct.field("high").to_numpy(),
            s.struct.field("low").to_numpy(),
            s.struct.field("close").to_numpy(),
            p,
            False # return_plus = False
        ), 
        return_dtype=pl.Float64
    )

    return [
        vortex_plus.alias(f"{indicator_str}__plus"),
        vortex_minus.alias(f"{indicator_str}__minus"),
    ]