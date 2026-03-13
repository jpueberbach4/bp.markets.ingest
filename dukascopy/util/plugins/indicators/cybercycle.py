import polars as pl
import numpy as np
from typing import List, Dict, Any

try:
    import numba
except ImportError:
    raise ImportError("Numba is required. Run 'pip install numba' OR 'pip install -r requirements.txt'")

from util.plugins.indicators.helpers.cybercycle_backend import _cybercycle_backend


def description() -> str:
    return (
        "Cyber Cycle by John Ehlers. "
        "A zero-lag oscillator that mathematically removes the trend component, "
        "isolating the pure cyclic wave of the market to pinpoint turning points."
    )


def meta() -> Dict:
    return {"author": "JP", "version": "1.0.0", "panel": 1, "verified": 1, "polars_input": 1}


def warmup_count(options: Dict[str, Any]) -> int:
    return 15


def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "period": args[0] if len(args) > 0 else "15"
    }


def calculate(df: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    period = float(options.get("period", 15.0))
    
    # Ehlers calculates alpha based on the cycle period
    alpha = 2.0 / (period + 1.0)

    # Ehlers typically calculates DSP indicators on the Median Price (H+L)/2
    if "high" in df.columns and "low" in df.columns:
        price_arr = ((df.get_column("high") + df.get_column("low")) / 2.0).to_numpy()
    else:
        price_arr = df.get_column("close").to_numpy()
        
    cycle, trigger = _cybercycle_backend(price_arr, alpha)
    
    # Load back into Polars and handle any trailing uninitialized gaps safely.
    # Note: Polars requires `fill_nan(None)` before `.forward_fill()` to work.
    return pl.DataFrame({
        "cyber_cycle": cycle,
        "trigger": trigger
    }).select([
        pl.col("cyber_cycle").fill_nan(None).forward_fill().backward_fill(),
        pl.col("trigger").fill_nan(None).forward_fill().backward_fill()
    ])