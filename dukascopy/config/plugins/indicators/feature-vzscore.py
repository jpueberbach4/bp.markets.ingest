import polars as pl
from typing import Dict, Any, List

def description() -> str:
    return (
        "Volume Z-Score (The Panic Detector). Measures how extreme the current volume is relative to the recent average.\n"
        " • Transform 'log': Best for ML Training. Compresses massive outliers (e.g., 100x spikes) into a stable range [-3, 5], preventing gradient explosions.\n"
        " • Transform 'nolog': Best for Human 'Sniper' signals. Preserves the raw magnitude of capitulation events (e.g., a 20-sigma spike)."
    )

def meta() -> Dict:
    return {
        "author": "Gemini",
        "version": 1.1,
        "panel": 1,
        "polars_input": 1,
        "category": "ML features"
    }

def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "window": args[0] if len(args) > 0 else "20",
        "transform": args[1] if len(args) > 1 else "log"
    }

def warmup_count(options: Dict[str, Any]) -> int:
    window = int(options.get("window", 20))
    return window + 1

def calculate(df: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    window = int(options.get("window", 20))
    transform_mode = options.get("transform", "log").lower()
    
    if transform_mode == "log":
        vol_series = pl.col("volume").log1p()
        prefix = "log"
    else:
        vol_series = pl.col("volume")
        prefix = "raw"

    rolling_mean = vol_series.rolling_mean(window_size=window)
    rolling_std = vol_series.rolling_std(window_size=window)

    z_score = (vol_series - rolling_mean) / (rolling_std + 1e-9)

    return df.select([
        z_score.alias(f"{prefix}")
    ])