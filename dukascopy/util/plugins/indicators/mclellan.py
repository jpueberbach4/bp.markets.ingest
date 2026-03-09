import polars as pl
from typing import List, Dict, Any

def description() -> str:
    return (
        "McClellan Oscillator and Summation Index: Calculates the difference between "
        "a fast and slow exponential moving average of (Advances - Declines). "
        "Useful for measuring market breadth and momentum."
    )

def meta() -> Dict:
    return {
        "author": "Google Gemini",
        "version": "1.0",
        "panel": 1,
        "verified": 1,
        "polars": 0,
        "polars_input": 1
    }

def warmup_count(options: Dict[str, Any]) -> int:
    slow_period = int(options.get("slow_period", 39))
    return slow_period * 3 + 50

def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "fast_period": args[0] if len(args) > 0 else "19",
        "slow_period": args[1] if len(args) > 1 else "39"
    }

def calculate(df: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    fast_period = int(options.get("fast_period", 19))
    slow_period = int(options.get("slow_period", 39))

    cols = df.columns

    if "advances" in cols and "declines" in cols:
        ad_expr = pl.col("advances") - pl.col("declines")
    elif "up_volume" in cols and "down_volume" in cols:
        ad_expr = pl.col("up_volume") - pl.col("down_volume")
    else:
        price_diff = pl.col("close").diff()
        
        if "volume" in cols:
            vol_expr = pl.col("volume")
        else:
            vol_expr = pl.lit(1.0)
            
        advances = pl.when(price_diff > 0).then(vol_expr).otherwise(0)
        declines = pl.when(price_diff < 0).then(vol_expr).otherwise(0)
        ad_expr = advances - declines

    calc_df = (
        df.select([
            ad_expr.alias("ad")
        ])
        .with_columns([
            pl.col("ad").ewm_mean(span=fast_period, adjust=False).alias("ema_fast"),
            pl.col("ad").ewm_mean(span=slow_period, adjust=False).alias("ema_slow")
        ])
        .with_columns([
            (pl.col("ema_fast") - pl.col("ema_slow")).alias("mcclellan_osc")
        ])
        .with_columns([
            pl.col("mcclellan_osc").cum_sum().alias("mcclellan_sum")
        ])
    )

    return calc_df.select(["mcclellan_osc", "mcclellan_sum"])