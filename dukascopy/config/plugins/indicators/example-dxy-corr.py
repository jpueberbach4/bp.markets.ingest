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
    # Import locally so startup is fast and this only loads when used
    from util.api import get_data
    import polars as pl

    # Hard-coded benchmark symbol (US Dollar Index)
    benchmark = "DOLLAR.IDX-USD"

    # The timeframe is the same for every row, so we read it once
    tf = df["timeframe"].item(0)

    # Incoming data is always sorted by time
    # So first and last rows give us the full time range instantly
    time_min = df["time_ms"][0]
    time_max = df["time_ms"][-1]

    # Extra history so joins don’t fail at the beginning
    # 5 days covers weekends + safety margin
    warmup_ms = 86400000 * 5 

    # ------------------------------------------------------------------
    # STEP 1: Load benchmark (DXY) price data
    # ------------------------------------------------------------------
    dxy_raw = get_data(
        symbol=benchmark,
        timeframe=tf,
        # Start earlier than needed so first joins have data
        after_ms=time_min - warmup_ms,
        # End slightly after last bar
        until_ms=time_max + 1,
        # Force Polars output so we can use lazy execution
        options={**options, "return_polars": True}
    )

    # If the API returns *no data at all*, joins would break
    # So we inject a fake row that produces a flat 0% line
    if dxy_raw.is_empty():
        dxy_lazy = (
            pl.DataFrame({
                # Single timestamp at the start
                "time_ms": [time_min],
                # Null close forces downstream logic to output 0.0
                "dxy_close": [None]
            })
            .lazy()
            .cast({"time_ms": pl.UInt64})
        )
    else:
        # Normal path: keep only what we need and sort for as-of join
        dxy_lazy = (
            dxy_raw
            .lazy()
            .select([
                pl.col("time_ms").cast(pl.UInt64),
                pl.col("close").alias("dxy_close")
            ])
            .sort("time_ms")
        )

    # ------------------------------------------------------------------
    # STEP 2: Prepare the main symbol (BASE) price stream
    # ------------------------------------------------------------------
    base_lazy = (
        df
        .lazy()
        # We only need time and close price
        .select([
            pl.col("time_ms").cast(pl.UInt64),
            pl.col("close").alias("base_close")
        ])
        # Required for as-of joins
        .sort("time_ms")
    )

    # ------------------------------------------------------------------
    # STEP 3: Join, normalize, and make everything safe
    # ------------------------------------------------------------------
    return (
        base_lazy
        # Match each EUR bar with the latest DXY bar *at or before* that time
        .join_asof(dxy_lazy, on="time_ms", strategy="backward")

        # Capture the first prices so we can normalize later
        .with_columns([
            # First EUR close becomes the 0% reference point
            pl.col("base_close").first().alias("base_start"),

            # First *valid* DXY close becomes the benchmark anchor
            # We skip nulls so empty datasets don’t poison the result
            pl.col("dxy_close")
              .filter(pl.col("dxy_close").is_not_null())
              .first()
              .alias("dxy_anchor")
        ])

        .with_columns([
            # EUR percent change from its starting value
            # If anything goes wrong, default to 0.0 instead of NaN
            ((pl.col("base_close") / pl.col("base_start")) - 1)
                .fill_null(0.0)
                .alias("base_pct"),

            # DXY percent change:
            # If there is no valid benchmark data, return a flat line at 0.0
            pl.when(
                pl.col("dxy_close").is_null() |
                pl.col("dxy_anchor").is_null()
            )
            .then(0.0)
            .otherwise((pl.col("dxy_close") / pl.col("dxy_anchor")) - 1)
            .alias("dxy_pct")
        ])

        # Only expose the final normalized series
        .select(["base_pct", "dxy_pct"])

        # Execute everything using streaming to keep memory usage low
        .collect(streaming=True)
    )
