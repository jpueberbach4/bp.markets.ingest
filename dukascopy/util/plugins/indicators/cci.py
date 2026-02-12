import numpy as np
import polars as pl
from typing import List, Dict, Any
from functools import partial

try:
    import numba
except ImportError:
    raise ImportError("Numba is required. Run 'pip install numba' OR 'pip install -r requirements.txt'")

from util.plugins.indicators.helpers.cci_backend import _cci_backend

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "Commodity Channel Index (CCI) measures the current price level relative "
        "to an average price level over a given period. It is used to identify "
        "new trends or warn of extreme overbought/oversold conditions."
    )

def meta() -> Dict:
    """
    Metadata for the dual-engine orchestrator.
    """
    return {
        "author": "Google Gemini",
        "version": 1.1,
        "panel": 1,
        "verified": 1,
        "talib-validated": 1, 
        "polars": 1,
    }

def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for CCI.
    """
    try:
        period = int(options.get('period', 20))
    except (ValueError, TypeError):
        period = 20
    return period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    """
    return {
        "period": args[0] if len(args) > 0 else "20"
    }

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    """
    Fast CCI implementation using the map_batches pattern.
    """
    try:
        p = int(options.get('period', 20))
    except (ValueError, TypeError):
        p = 20

    tp_expr = (pl.col("high") + pl.col("low") + pl.col("close")) / 3.0
    
    cci_expr = tp_expr.map_batches(
        lambda s: _cci_backend(s.to_numpy(), p),
        return_dtype=pl.Float64
    )

    direction_expr = (
        pl.when(cci_expr > cci_expr.shift(1))
        .then(100)
        .otherwise(-100)
        .cast(pl.Int32)
    )

    return [
        cci_expr.alias(indicator_str),
        direction_expr.alias("direction")
    ]
