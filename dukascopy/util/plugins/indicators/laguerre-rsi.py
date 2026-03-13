import polars as pl
import numpy as np
from typing import List, Dict, Any

try:
    import numba
except ImportError:
    raise ImportError("Numba is required. Run 'pip install numba' OR 'pip install -r requirements.txt'")

from util.plugins.indicators.helpers.laguerrersi_backend import _laguerrersi_backend


def description() -> str:
    return (
        "Laguerre RSI by John Ehlers. "
        "Applies a 4-pole DSP Laguerre filter to create an ultra-smooth, zero-lag "
        "momentum oscillator. Perfect for neural network feature spaces to prevent noise."
    )

def meta() -> Dict:
    return {"author": "JP", "version": "1.0.0", "panel": 1, "verified": 1, "polars_input": 1}


def warmup_count(options: Dict[str, Any]) -> int:
    return 50

def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "gamma": args[0] if len(args) > 0 else "0.5"
    }


def calculate(df: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    gamma = float(options.get("gamma", 0.5))

    price_arr = df.get_column("close").to_numpy()
        
    rsi = _laguerrersi_backend(price_arr, gamma)
    
    return pl.DataFrame({
        "laguerre_rsi": rsi
    }).select([
        pl.col("laguerre_rsi").fill_nan(None).forward_fill().backward_fill()
    ])