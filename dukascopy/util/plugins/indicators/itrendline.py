import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any
from functools import partial

try:
    import numba
except ImportError:
    raise ImportError("Numba is required. Run 'pip install numba' OR 'pip install -r requirements.txt'")

from util.plugins.indicators.helpers.itrendline_backend import _itrendline_backend

def description() -> str:
    return (
        "Instantaneous Trendline (iTrend) by John Ehlers. "
        "A near-zero-lag trend indicator that filters out cyclical components "
        "to reveal the true underlying trend of the market."
    )


def meta() -> Dict:
    return {"author": "JP", "version": "1.0.0", "panel": 0, "verified": 1, "polars_input": 1}


def warmup_count(options: Dict[str, Any]) -> int:
    return 60


def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "alpha": args[0] if len(args) > 0 else "0.07"
    }


def calculate(df: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    alpha = float(options.get("alpha", 0.07))

    if "high" in df.columns and "low" in df.columns:
        price_arr = ((df.get_column("high") + df.get_column("low")) / 2.0).to_numpy()
    else:
        price_arr = df.get_column("close").to_numpy()
        
    it, trigger = _itrendline_backend(price_arr, alpha)
    
    return pl.DataFrame({
        "itrend": it,
        "itrend_trigger": trigger
    }).select([
        pl.col("itrend").fill_nan(None).forward_fill().backward_fill(),
        pl.col("itrend_trigger").fill_nan(None).forward_fill().backward_fill()
    ])