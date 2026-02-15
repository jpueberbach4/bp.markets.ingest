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

def calculate(df: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    # Import here so the engine only loads this when the indicator runs
    from util.api import get_data
    import polars as pl

    # Hardcoded benchmark symbol we compare against
    benchmark = "DOLLAR.IDX-USD"

    # Timeframe of the incoming dataframe (e.g. 1h, 4h, 1d)
    # Assumed constant for the whole chunk
    tf = df["timeframe"].item(0)

    # We assume df is already sorted by time_ms
    # So first row = earliest timestamp, last row = latest timestamp
    time_min, time_max = df["time_ms"][0], df["time_ms"][-1]

    # Fetch benchmark (DXY) data slightly before our window
    # The extra 5 days ensures we have a valid anchor even across weekends / gaps
    dxy_raw = get_data(
        symbol=benchmark,
        timeframe=tf,
        after_ms=time_min - (86400000 * 5),
        until_ms=time_max + 1,
        options={**options, "return_polars": True}
    )

    # Convert benchmark data to lazy mode (no execution yet)
    # Keep only time and close price
    # Rename close -> dxy_close so it doesn’t collide later
    # Sort is REQUIRED for join_asof to work correctly
    dxy_lazy = (
        dxy_raw
        .lazy()
        .select([
            pl.col("time_ms").cast(pl.UInt64),
            pl.col("close").alias("dxy_close")
        ])
        .sort("time_ms")
    )

    return (
        # Convert the incoming dataframe to lazy mode
        df
        .lazy()

        # Keep only what we need: time and base asset close price
        .select([
            pl.col("time_ms").cast(pl.UInt64),
            pl.col("close").alias("base_close")
        ])

        # Sort for join_asof safety
        .sort("time_ms")

        # Temporal join:
        # For each base candle, attach the LAST known DXY candle at or before that time
        .join_asof(dxy_lazy, on="time_ms", strategy="backward")

        # Compute anchors (reference prices)
        .with_columns([
            # base_start = first base_close in the entire window
            # Used to normalize the base asset
            pl.col("base_close").first().alias("base_start"),

            # dxy_anchor = first NON-null DXY close
            # drop_nulls avoids picking a missing value as the anchor
            pl.col("dxy_close").drop_nulls().first().alias("dxy_anchor")
        ])

        # Convert prices into percentage performance series
        .select([
            # Base asset percent change from its starting price
            # (price / start) - 1
            # fill_null(0.0) prevents NaNs at the beginning
            ((pl.col("base_close") / pl.col("base_start")) - 1)
                .fill_null(0.0)
                .alias("base_pct"),

            # DXY percent change from its anchor price
            # If DXY data is missing, result becomes null → filled to 0.0
            ((pl.col("dxy_close") / pl.col("dxy_anchor")) - 1)
                .fill_null(0.0)
                .alias("dxy_pct")
        ])

        # Execute the lazy query
        # streaming=True keeps memory usage low on large datasets
        .collect(streaming=True)
    )

