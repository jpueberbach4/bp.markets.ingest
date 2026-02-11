import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

try:
    import numba
except ImportError:
    raise ImportError("Numba is required. Run 'pip install numba' OR 'pip install -r requirements.txt'")

from util.plugins.indicators.helpers.psar_backend import _psar_backend

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "The Parabolic SAR (Stop and Reverse) is a trend-following indicator used to "
        "identify potential reversals in price movement. It appears as a series of "
        "dots placed either above or below the price: dots below indicate a bullish "
        "trend, while dots above indicate a bearish trend. The indicator 'accelerates' "
        "as the trend continues, moving closer to the price to provide dynamic trailing "
        "stop-loss levels."
    )

def meta() -> Dict:
    """
    Metadata for the dual-engine orchestrator.
    """
    return {
        "author": "Google Gemini",
        "version": 1.2,
        "verified": 1,
        "talib-validated": 1, 
        "polars": 1
    }

def warmup_count(options: Dict[str, Any]) -> int:
    """
    PSAR requires a warmup to establish the correct trend direction and 
    acceleration factor stability. 100 bars is the industry standard.
    """
    return 100

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: psar_0.02_0.2 -> {'step': '0.02', 'max_step': '0.2'}
    """
    return {
        "step": args[0] if len(args) > 0 else "0.02",
        "max_step": args[1] if len(args) > 1 else "0.2"
    }


def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> pl.Expr:
    """
    High-performance Polars-native calculation for PSAR.
    Uses map_batches to execute the recursive state machine in a single pass.
    """
    import numba
    try:
        step = float(options.get('step', 0.02))
        max_step = float(options.get('max_step', 0.2))
    except (ValueError, TypeError):
        step, max_step = 0.02, 0.2

    return pl.struct(["high", "low"]).map_batches(
        lambda s: _psar_backend(
            s.struct.field("high").to_numpy(),
            s.struct.field("low").to_numpy(),
            step, 
            max_step
        )
    ).alias(indicator_str)

