import polars as pl
from typing import List, Dict, Any

try:
    import numba
except ImportError:
    raise ImportError("Numba is required. Run 'pip install numba' OR 'pip install -r requirements.txt'")

from util.plugins.indicators.helpers.supersmoother_backend import _supersmoother_backend

def description() -> str:
    return (
        "SuperSmoother Filter by John Ehlers. "
        "A 2-pole low-pass filter that effectively removes high-frequency aliasing noise "
        "from price data with significantly less lag than a traditional EMA or SMA."
    )


def meta() -> Dict:
    return {"author": "JP", "version": "1.0.0", "panel": 0, "verified": 1, "polars_input": 1}


def warmup_count(options: Dict[str, Any]) -> int:
    return 60


def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "period": args[0] if len(args) > 0 else "10"
    }


def calculate(df: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    period = float(options.get("period", 10.0))

    # Ehlers typically applies smoothing to the Median Price (H+L)/2
    if "high" in df.columns and "low" in df.columns:
        price_arr = ((df.get_column("high") + df.get_column("low")) / 2.0).to_numpy()
    else:
        price_arr = df.get_column("close").to_numpy()
        
    supersmoother_line = _supersmoother_backend(price_arr, period)
    
    # Load back into Polars and handle any trailing uninitialized gaps safely.
    return pl.DataFrame({
        "supersmoother": supersmoother_line
    }).select([
        pl.col("supersmoother").fill_nan(None).forward_fill().backward_fill()
    ])