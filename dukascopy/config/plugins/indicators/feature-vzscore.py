import polars as pl
from typing import Dict, Any, List

def description() -> str:
    return (
        "Volume Z-Score: Normalizes volume to standard deviations from the mean."
        ""
        "Use transform=[log|nolog], log for ML to handle massive outlier skew."
    )

def meta() -> Dict:
    return {
        "author": "Gemini",
        "version": 1.0,
        "panel": 1,
        "polars_input": 1,
        "category": "ML features"
    }

def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "window": args[0] if len(args) > 0 else "14",
        "transform": args[1] if len(args) > 1 else "log"
    }

def warmup_count(options: Dict[str, Any]) -> int:
    window = int(options.get("window", 20))
    return window + 1

def calculate(df: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    window = int(options.get("window", 20))
    use_log = options.get("transform", "log")=="log"
    
    if use_log:
        vol_series = pl.col("volume").log1p()
        prefix = "log_vol"
        print("use log")
    else:
        print("no log")
        vol_series = pl.col("volume")
        prefix = "vol"

    rolling_mean = vol_series.rolling_mean(window_size=window)
    rolling_std = vol_series.rolling_std(window_size=window)

    z_score = (vol_series - rolling_mean) / (rolling_std + 1e-9)

    return df.select([
        z_score.alias(f"{prefix}_zscore_{window}")
    ])