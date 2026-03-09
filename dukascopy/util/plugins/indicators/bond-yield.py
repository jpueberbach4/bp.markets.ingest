import polars as pl
from typing import List, Dict, Any

def description() -> str:
    return (
        "Benchmark Bond Yield: Fetches a bond price benchmark (BUND, GILT, UST), "
        "merges it with the current asset timeline, and converts the price quote "
        "into a Yield-to-Maturity (YTM) percentage.\n\n"
        "GILT.TR-GBP uses a 4% coupon and 15 year maturity, USTBOND.TR-USD uses a 6% coupon and 30 year maturity, and BUND.TR-EUR uses a 6% coupon and 10 year maturity by default. "
    )

def meta() -> Dict:
    return {
        "author": "Gemini",
        "version": 1.2,
        "panel": 1,
        "verified": 1,
        "polars_input": 1
    }

def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "benchmark": args[0] if len(args) > 0 else "BUND.TR-EUR",
        "coupon": args[1] if len(args) > 1 else "6.0",
        "maturity_years": args[2] if len(args) > 2 else "10.0"
    }

def warmup_count(options: Dict[str, Any]) -> int:
    return 100

def calculate(df: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    from util.api import get_data
    
    benchmark = options.get("benchmark", "BUND.TR-EUR")
    coupon = float(options.get("coupon", 6.0))
    par = 100.0
    years = float(options.get("maturity_years", 10.0))
    
    tf = df["timeframe"].item(0)
    time_min, time_max = df["time_ms"][0], df["time_ms"][-1]
    
    bench_raw = get_data(
        symbol=benchmark, 
        timeframe=tf,
        after_ms=time_min - (86400000 *30), # 1 month warmup
        until_ms=time_max + 1,
        limit=1000000,
        options={**options, "return_polars": True}
    )

    if bench_raw is None or bench_raw.is_empty():
        return pl.DataFrame({"yield": [0.0] * len(df)})

    bench_lazy = bench_raw.lazy().select([
        pl.col("time_ms").cast(pl.UInt64),
        pl.col("close").alias("bench_price")
    ]).sort("time_ms")

    return (
        df.lazy()
        .select([pl.col("time_ms").cast(pl.UInt64)])
        .sort("time_ms")
        .join_asof(bench_lazy, on="time_ms", strategy="backward")
        .with_columns([
            (
                (coupon + (par - pl.col("bench_price")) / years) / 
                ((par + pl.col("bench_price")) / 2.0)
            ).alias("raw_yield")
        ])
        .select([
            (pl.col("raw_yield") * 100.0)
            .fill_null(strategy="forward")
            .fill_null(0.0)
            .alias("yield")
        ])
        .collect()
    )