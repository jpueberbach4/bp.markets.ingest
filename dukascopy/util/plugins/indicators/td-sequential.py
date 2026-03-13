import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

try:
    import numba
except ImportError:
    raise ImportError("Numba is required. Run 'pip install numba' OR 'pip install -r requirements.txt'")

from util.plugins.indicators.helpers.tdsequential_backend import _tdsequential_backend


def description() -> str:
    return (
        "TD Sequential by Tom DeMark. "
        "A strict, zero-lag bar counting system that identifies structural exhaustion. "
        "Outputs the 1-9 Setup phase and the 1-13 Countdown phase to pinpoint exact tops and bottoms."
    )


def meta() -> Dict:
    return {"author": "JP", "version": "1.0.0", "panel": 1, "verified": 1, "polars_input": 1}


def warmup_count(options: Dict[str, Any]) -> int:
    return 30


def position_args(args: List[str]) -> Dict[str, Any]:
    return {}


def calculate(df: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    close_arr = df.get_column("close").to_numpy()
    high_arr = df.get_column("high").to_numpy()
    low_arr = df.get_column("low").to_numpy()
        
    setup, countdown = _tdsequential_backend(close_arr, high_arr, low_arr)
    
    # Load back into Polars. We use 0 for "no active count".
    return pl.DataFrame({
        "td_setup": setup,
        "td_countdown": countdown
    })