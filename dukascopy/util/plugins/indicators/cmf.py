import polars as pl
import numpy as np
from typing import List, Dict, Any

try:
    import numba
except ImportError:
    raise ImportError("Numba is required. Run 'pip install numba' OR 'pip install -r requirements.txt'")

from util.plugins.indicators.helpers.cmf_backend import _cmf_backend

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "Chaikin Money Flow (CMF) measures the amount of Money Flow Volume over a specific period. "
        "It combines price and volume to show how buying and selling pressure is distributed. "
        "A CMF above zero indicates buying pressure (accumulation), while a CMF below zero indicates "
        "selling pressure (distribution)."
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
    Calculates the required warmup rows for the CMF Indicator.
    Requires a full rolling sum window to stabilize.
    """
    try:
        period = int(options.get('period', 20))
    except (ValueError, TypeError):
        period = 20
    return period

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    """
    return {
        "period": args[0] if len(args) > 0 else "20"
    }

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    p = int(options.get('period', 20))

    # We pack the necessary columns into a struct to pass to map_batches
    cmf = pl.struct(["high", "low", "close", "volume"]).map_batches(
        lambda s: _cmf_backend(
            s.struct.field("high").to_numpy(),
            s.struct.field("low").to_numpy(),
            s.struct.field("close").to_numpy(),
            s.struct.field("volume").to_numpy(),
            p
        ), 
        return_dtype=pl.Float64
    )

    return [
        cmf.alias(f"{indicator_str}"),
    ]