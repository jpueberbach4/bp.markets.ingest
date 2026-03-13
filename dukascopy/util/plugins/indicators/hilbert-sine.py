import polars as pl
import numpy as np
from typing import List, Dict, Any

try:
    import numba
except ImportError:
    raise ImportError("Numba is required. Run 'pip install numba' OR 'pip install -r requirements.txt'")

from util.plugins.indicators.helpers.hilbertsine_backend import _hilbertsine_backend

def description() -> str:
    return (
        "Hilbert Transform Sine Wave by John Ehlers. "
        "Splits price into InPhase and Quadrature components to dynamically calculate "
        "the market's dominant cycle phase. Crossovers pinpoint tops and bottoms with zero lag."
    )


def meta() -> Dict:
    return {"author": "JP", "version": "1.0.0", "panel": 1, "verified": 1, "polars_input": 1}


def warmup_count(options: Dict[str, Any]) -> int:
    # Requires an extended warmup to allow the recursive FIR filters and period estimators to settle
    return 60


def position_args(args: List[str]) -> Dict[str, Any]:
    # The Hilbert Transform is adaptive and requires no fixed period parameter
    return {}


def calculate(df: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    # Ehlers mathematically demands calculating DSP indicators on the Median Price (H+L)/2
    if "high" in df.columns and "low" in df.columns:
        price_arr = ((df.get_column("high") + df.get_column("low")) / 2.0).to_numpy()
    else:
        price_arr = df.get_column("close").to_numpy()
        
    sine, leadsine = _hilbertsine_backend(price_arr)
    
    # Load back into Polars and handle any trailing uninitialized gaps safely.
    return pl.DataFrame({
        "hilbert_sine": sine,
        "hilbert_leadsine": leadsine
    }).select([
        pl.col("hilbert_sine").fill_nan(None).forward_fill().backward_fill(),
        pl.col("hilbert_leadsine").fill_nan(None).forward_fill().backward_fill()
    ])