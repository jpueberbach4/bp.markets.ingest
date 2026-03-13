
import polars as pl
import numpy as np
from typing import List, Dict, Any

try:
    import numba
except ImportError:
    raise ImportError("Numba is required. Run 'pip install numba' OR 'pip install -r requirements.txt'")

from util.plugins.indicators.helpers.cg_backend import _cg_backend

def description() -> str:
    return (
        "Center of Gravity (CG) Oscillator by John Ehlers. "
        "An FIR filter that identifies major turning points with essentially zero lag "
        "by measuring the shifting center of balance of price action."
    )


def meta() -> Dict:
    return {"author": "JP", "version": "1.0.0", "panel": 1, "verified": 1, "polars_input": 1}


def warmup_count(options: Dict[str, Any]) -> int:
    return int(options.get("period", 10))


def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "period": args[0] if len(args) > 0 else "10"
    }


def calculate(df: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    period = int(options.get("period", 10))

    if "high" in df.columns and "low" in df.columns:
        price_arr = ((df.get_column("high") + df.get_column("low")) / 2.0).to_numpy()
    else:
        price_arr = df.get_column("close").to_numpy()
        
    cg, trigger = _cg_backend(price_arr, period)
    
    return pl.DataFrame({
        "cg": cg,
        "trigger": trigger
    }).select([
        pl.col("cg").fill_nan(None).forward_fill().backward_fill(),
        pl.col("trigger").fill_nan(None).forward_fill().backward_fill()
    ])