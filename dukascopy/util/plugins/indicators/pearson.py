import polars as pl
from typing import List, Dict, Any

def description() -> str:
    return (
        "Calculates the Rolling Pearson Correlation between the current asset and a benchmark (target) asset.\n"
        "Values oscillate between +1.0 (perfectly synced) and -1.0 (perfectly inverse). \n"
        "When data is unavailable for a historic period on one of the assets it displays 0.0\n"
    )

def meta() -> Dict:
    return {
        "author": "Gemini",
        "version": 1.1,
        "panel": 1,
        "verified": 1,
        "polars_input": 1
    }

def position_args(args: List[str]) -> Dict[str, Any]:
    return {"benchmark": args[0] if len(args) > 0 else "DOLLAR.IDX-USD"}

def warmup_count(options: Dict[str, Any]):
    return 500

def calculate(df: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    from util.api import get_data
    import polars as pl

    benchmark = options.get("benchmark", "DOLLAR.IDX-USD")
    tf = df["timeframe"].item(0)
    time_min, time_max = df["time_ms"][0], df["time_ms"][-1]
    
    dxy_raw = get_data(
        symbol=benchmark, timeframe=tf,
        after_ms=time_min - (86400000 * 14),
        until_ms=time_max + 1,
        limit=1000000,
        options={**options, "return_polars": True}
    )

    dxy_lazy = dxy_raw.lazy().select([
        pl.col("time_ms").cast(pl.UInt64),
        pl.col("close").alias("dxy_close")
    ]).sort("time_ms")

    return (
        df.lazy()
        .select([
            pl.col("time_ms").cast(pl.UInt64),
            pl.col("close").cast(pl.Float64).alias("base_close")
        ])
        .sort("time_ms")
        .join_asof(dxy_lazy, on="time_ms", strategy="backward")
        .with_columns([
            (pl.col("base_close") / pl.col("base_close").shift(1) - 1).alias("base_ret"),
            (pl.col("dxy_close") / pl.col("dxy_close").shift(1) - 1).alias("dxy_ret")
        ])
        .select([
            pl.rolling_corr(
                pl.col("base_ret"), 
                pl.col("dxy_ret"), 
                window_size=30
            )
            .fill_null(0.0)
            .round(6)
            .alias("correlation")
        ])
        .collect(streaming=True)
    )