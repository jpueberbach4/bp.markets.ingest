import polars as pl
from typing import Dict, Any, List

def description() -> str:
    return (
        "ML Moving Average Distance. Normalizes MAs by calculating the percentage offset from price.\n"
        " • Use (Price / MA - 1): Converts absolute price levels into a stationary percentage (e.g., +0.02 for 2% above MA).\n"
        " • Mode 'sma': Simple Moving Average. Best for long-term mean reversion baselines.\n"
        " • Mode 'ema': Exponential Moving Average. Best for trend-following features (reacts faster to price shifts)."
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
        "window": args[0] if len(args) > 0 else "20",
        "mode": args[1] if len(args) > 1 else "sma",
        "target-col": args[2] if len(args) > 2 else "close",
    }

def warmup_count(options: Dict[str, Any]) -> int:
    window = int(options.get("window", 20))
    mode = options.get("mode", "sma").lower()
    
    if mode == "ema":
        return window * 3
    return window

def calculate(df: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    window = int(options.get("window", 20))
    mode = options.get("mode", "sma").lower()
    target_col = options.get("target-col", "close")
    
    if target_col not in df.columns:
        target_col = "close"
        
    price = pl.col(target_col)

    if mode == "ema":
        ma = price.ewm_mean(alpha=1.0/window, adjust=False)
    else:
        ma = price.rolling_mean(window_size=window)

    dist_ratio = (price / (ma + 1e-9)) - 1.0

    return df.select([
        dist_ratio.alias(f"{target_col}_{mode}_{window}_dist")
    ])