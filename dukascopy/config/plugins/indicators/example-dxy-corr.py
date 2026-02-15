import polars as pl
from typing import List, Dict, Any

def description() -> str:
    return (
            "Current pair vs Dollar Index (DXY) Comparison. Normalizes both to % change to spot divergences."
            "Note: Requires DOLLAR.IDX-USD to be configured."
            "Note: the DOLLAR index doesnt have the same history as EUR-USD. Meaning that far in history you"
            "wont see the DXY line. Eg DOLLAR.IDX-USD starts from 2017 and EUR-USD starts from 2005. Data-gaps "
            "like this we cant fix, so we display a flat line for DXY. Provider doesnt have more history."
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

    benchmark = "DOLLAR.IDX-USD"
    tf = df["timeframe"].item(0)
    
    # This ensures the "Zero" reference is always N bars behind the current bar
    period = warmup_count({}) 
    
    time_min, time_max = df["time_ms"][0], df["time_ms"][-1]
    
    # Fetch DXY with massive limit to prevent truncation
    # We look back 'period' bars + buffer to ensure we can calculate the shift
    dxy_raw = get_data(
        symbol=benchmark,
        timeframe=tf,
        after_ms=time_min - (86400000 * 20), # generous buffer for the 1000 bar lookup
        until_ms=time_max + 1,
        limit=1000000,
        options={**options, "return_polars": True}
    )

    dxy_lazy = (
        dxy_raw.lazy()
        .select([
            pl.col("time_ms").cast(pl.UInt64),
            pl.col("close").alias("dxy_close")
        ])
        .sort("time_ms")
    )

    # Join and Calculate Rolling % Change (Window-Invariant)
    return (
        df.lazy()
        .select([
            pl.col("time_ms").cast(pl.UInt64),
            pl.col("close").alias("base_close")
        ])
        .sort("time_ms")
        .join_asof(dxy_lazy, on="time_ms", strategy="backward")
        .select([
            # If period is N, this shows "Performance over the last N bars"
            ((pl.col("base_close") / pl.col("base_close").shift(period)) - 1)
                .fill_null(0.0)
                .alias("base_pct"),
            
            # If the history (t - 1000) doesn't exist (pre-2017), result is null -> 0.0 flatline
            ((pl.col("dxy_close") / pl.col("dxy_close").shift(period)) - 1)
                .fill_null(0.0)
                .alias("dxy_pct")
        ])
        .collect(streaming=True)
    )