import polars as pl
from typing import List, Dict, Any

def description() -> str:
    return (
            "Current pair vs Dollar Index (DXY) Comparison. Normalizes both to % change to spot divergences."
            "This one adds an smoothed histogram op top of the base one. It shows how to extend an "
            "existing indicator.\n\n"
            "Note: Requires DOLLAR.IDX-USD to be configured. Example for demonstration purposes."
    )

def meta() -> Dict:
    return {
        "author": "Gemini",
        "version": 1.0,
        "panel": 1,
        "verified": 1,
        "polars_input": 1
    }

def position_args(args: List[str]) -> Dict[str, Any]:
    return {
    }

def warmup_count(options: Dict[str, Any]):
    return 500

def calculate(df: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    from util.api import get_data
    import polars as pl

    symbol = df["symbol"].item(0)
    tf = df["timeframe"].item(0)
    smooth_period = 2  # Your SMA window
    
    time_min, time_max = df["time_ms"][0], df["time_ms"][-1]
    
    dxy_raw = get_data(
        symbol=symbol,
        timeframe=tf,
        after_ms=time_min - (86400000 * 20),
        until_ms=time_max + 1,
        limit=1000000,
        indicators=['example-dxy-corr-base'],
        options={**options, "return_polars": True}
    )

    dxy_indicators = (
        dxy_raw.lazy()
        .select([
            pl.col("time_ms").cast(pl.UInt64),
            pl.col("example-dxy-corr-base__base_pct").alias("base_pct"),
            pl.col("example-dxy-corr-base__dxy_pct").alias("dxy_pct")
        ])
        .sort("time_ms")
    )

    return (
        df.lazy()
        .select([pl.col("time_ms").cast(pl.UInt64)])
        .sort("time_ms")
        .join_asof(dxy_indicators, on="time_ms", strategy="backward")
        .with_columns([
            pl.when((pl.col("base_pct") == 0.0) | (pl.col("dxy_pct") == 0.0))
              .then(0.0)
              .otherwise(pl.col("base_pct") - pl.col("dxy_pct"))
              .alias("raw_width")
        ])
        .with_columns([
            pl.col("raw_width")
              .rolling_mean(window_size=smooth_period)
              .fill_null(0.0)
              .alias("hist")
        ])
        .select([
            "base_pct",
            "dxy_pct",
            "hist"
        ])
        .collect(streaming=True)
    )
