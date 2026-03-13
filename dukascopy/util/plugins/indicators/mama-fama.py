import polars as pl
import numpy as np
from typing import List, Dict, Any

try:
    import numba
except ImportError:
    raise ImportError("Numba is required. Run 'pip install numba' OR 'pip install -r requirements.txt'")

from util.plugins.indicators.helpers.mama_backend import _mama_backend


def description() -> str:
    return (
        "MESA Adaptive Moving Average (MAMA) & Following Adaptive Moving Average (FAMA). "
        "Developed by John Ehlers, this indicator uses the Hilbert Transform to adapt to "
        "market cycles. Optimized via Numba and Polars."
    )


def meta() -> Dict:
    return {"author": "JP", "version": "1.1.0", "panel": 0, "verified": 1, "polars_input": 1}


def warmup_count(options: Dict[str, Any]) -> int:
    return 60


def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "fastlimit": args[0] if len(args) > 0 else "0.5",
        "slowlimit": args[1] if len(args) > 1 else "0.05"
    }


def calculate(df: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    fastlimit = float(options.get('fastlimit', 0.5))
    slowlimit = float(options.get('slowlimit', 0.05))

    if "high" in df.columns and "low" in df.columns:
        price_arr = ((df.get_column("high") + df.get_column("low")) / 2.0).to_numpy()
    else:
        price_arr = df.get_column("close").to_numpy()
        
    mama, fama = _mama_backend(price_arr, fastlimit, slowlimit)
    
    return pl.DataFrame({
        "mama": mama,
        "fama": fama
    }).select([
        pl.col("mama").fill_nan(None).forward_fill().backward_fill(),
        pl.col("fama").fill_nan(None).forward_fill().backward_fill()
    ])