import polars as pl
from typing import List, Dict, Any

def description() -> str:
    return (
        "Volume Acceleration (Local): Measures the second derivative of the volume "
        "already present in the DataFrame. Detects 'Selling Climaxes' and "
        "institutional absorption at market bottoms."
    )

def meta() -> Dict:
    return {
        "author": "Google Gemini",
        "version": 1.1,
        "panel": 1,
        "verified": 1,
        "polars": 0,
        "polars_input": 1
    }

def warmup_count(options: Dict[str, Any]) -> int:
    return int(options.get("period", 10)) * 2

def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "period": args[0] if len(args) > 0 else "10",
    }

def calculate(df: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    """
    Calculates Volume Acceleration (d2V/dt2) using the existing volume column.
    Optimized for zero-latency ML feature generation.
    """
    period = int(options.get("period", 10))

    return (
        df.lazy()
        .with_columns([
            (pl.col("volume") - pl.col("volume").shift(1)).alias("vol_vel")
        ])
        .with_columns([
            (pl.col("vol_vel") - pl.col("vol_vel").shift(1)).alias("vol_accel_raw")
        ])
        .with_columns([
            (
                pl.col("vol_accel_raw") / 
                pl.col("vol_accel_raw").rolling_std(window_size=period)
            ).alias("acceleration")
        ])
        .select([
            pl.col("acceleration").fill_null(0.0).fill_nan(0.0)
        ])
        .collect(streaming=True)
    )