import polars as pl
import numpy as np
from typing import Dict, Any, List
from functools import partial

try:
    import numba
except ImportError:
    raise ImportError("Numba is required. Run 'pip install numba' OR 'pip install -r requirements.txt'")

from util.plugins.indicators.helpers.swingpoints_backend import _swingpoints_backend


def description() -> str:
    return (
        "Swing Points (Fractals): Identifies local Highs and Lows. "
        "Standard Williams Fractal = 2 Left, 2 Right. "
        "Useful for placing stops or identifying Market Structure Breaks (MSB)."
    )

def meta() -> Dict:
    return {
        "author": "Google Gemini",
        "version": 1.0,
        "panel": 0,
        "verified": 1,
        "polars": 1
    }

def warmup_count(options: Dict[str, Any]) -> int:
    try:
        left = int(options.get('left', 2))
        right = int(options.get('right', 2))
        return left + right + 1
    except:
        return 5

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Args: left_strength, right_strength
    Example: 2,2 (Williams) or 5,5 (Major Swing)
    """
    return {
        "left": args[0] if len(args) > 0 else "2",
        "right": args[1] if len(args) > 1 else "2"
    }

def _swingpoints_map_wrapper(s: pl.Series, left: int, right: int) -> pl.Series:
    """
    Wrapper to extract buffers and return a Polars Struct.
    """
    highs = s.struct.field("high").to_numpy()
    lows = s.struct.field("low").to_numpy()
    
    sh, sl = _swingpoints_backend(highs, lows, left, right)
    
    return pl.DataFrame({
        "swing_high": sh,
        "swing_low": sl
    }).to_struct("swing_results")

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    """
    High-performance Pivot/Swing Point detection for Polars.
    """
    l = int(options.get('left', 2))
    r = int(options.get('right', 2))

    mapper = partial(_swingpoints_map_wrapper, left=l, right=r)

    swing_schema = pl.Struct([
        pl.Field("swing_high", pl.Float64),
        pl.Field("swing_low", pl.Float64),
    ])

    swing_base = (
        pl.struct(["high", "low"])
        .map_batches(mapper, return_dtype=swing_schema)
    )

    return [
        swing_base.struct.field("swing_high").alias(f"{indicator_str}__high"),
        swing_base.struct.field("swing_low").alias(f"{indicator_str}__low")
    ]
