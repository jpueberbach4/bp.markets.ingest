import polars as pl
from typing import List, Dict, Any

try:
    import numba
except ImportError:
    raise ImportError("Numba is required. Run 'pip install numba' OR 'pip install -r requirements.txt'")

from util.plugins.indicators.helpers.fishertransform_backend import _fishertransfrom_backend

def description() -> str:
    return (
        "The Fisher Transform by John Ehlers. "
        "Converts prices into a Gaussian normal distribution. Turns lagging, pegged "
        "momentum plateaus into incredibly sharp, distinct turning points with nearly zero lag."
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
        
    fisher, trigger = _fishertransfrom_backend(price_arr, period)
    
    return pl.DataFrame({
        "fisher": fisher,
        "trigger": trigger
    }).select([
        pl.col("fisher").fill_nan(None).forward_fill().backward_fill(),
        pl.col("trigger").fill_nan(None).forward_fill().backward_fill()
    ])