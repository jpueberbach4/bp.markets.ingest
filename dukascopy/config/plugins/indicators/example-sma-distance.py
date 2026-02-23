import polars as pl
from typing import List, Dict, Any

def description() -> str:
    return (
        "Orbit Distance: Measures the relative distance of an asset price to its SMA orbit. "
        "Returns a ratio: (Price / SMA). Values > 1.0 indicate overhead stretch; < 1.0 indicate undershoot. "
        "Strictly optimized for ML feature engineering with O(1) time range lookups."
    )

def meta() -> Dict:
    return {
        "author": "Gemini",
        "version": 1.0, 
        "panel": 1,
        "verified": 1,
        "polars_input": 1
    }

def warmup_count(options: Dict[str, Any]) -> int:
    return int(options.get("period", 200))

def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "benchmark": args[0] if len(args) > 0 else "{symbol}",
        "period": args[1] if len(args) > 1 else "200",
    }

def calculate(df: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    from util.api import get_data
    import polars as pl

    symbol = options.get("benchmark", "{symbol}")
    period = int(options.get("period", 200))
    sma_col = f"sma_{period}"
    
    time_min = df["time_ms"][0]
    time_max = df["time_ms"][-1]
    
    warmup_ms = 86400000 * 60 * period 

    data = get_data(
        symbol=symbol,
        timeframe=df["timeframe"].item(0),
        after_ms=time_min - warmup_ms,
        until_ms=time_max + 1,
        indicators=[sma_col, "is-open"],
        limit=1000000,
        options={**options, "return_polars": True}
    )

    if data.is_empty():
        return pl.DataFrame({
            "dist": pl.Series([], dtype=pl.Float64)
        })
   
    source_lazy = (
        data.lazy()
        .filter(pl.col("is-open") == 0)
        .select([
            pl.col("time_ms").cast(pl.UInt64),
            (pl.col("close") / pl.col(sma_col)).alias("dist")
        ])
    )

    timeline = df.select([pl.col("time_ms").cast(pl.UInt64)]).lazy()

    result = (
        timeline
        .join_asof(source_lazy, on="time_ms", strategy="backward")
        .select("dist")
        .collect(streaming=True)
    )

    return result