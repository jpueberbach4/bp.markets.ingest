import polars as pl
import pandas as pd
import numpy as np
from typing import List, Dict, Any

def description() -> str:
    # Return a human-readable explanation of what this indicator does
    return (
        "Drift displays the current drift in minutes relative to the BTC-USD heartbeat symbol."
    )

def meta() -> Dict:
    # Metadata used by the platform to identify and validate this indicator
    return {
        "author": "JP",             # Who wrote this
        "version": 1.0,             # Version number
        "panel": 1,                 # UI panel placement
        "verified": 1,              # Marked as verified
        "polars": 0,                # Does not require polars output by default
        "polars_input": 1           # Expects polars input
    }

def warmup_count(options: Dict[str, Any]) -> int:
    # Number of candles needed before this indicator can run
    # Zero means it can run immediately
    return 0

def position_args(args: List[str]) -> Dict[str, Any]:
    # This indicator does not use any positional arguments
    return {}

def calculate(df: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    # Import here to avoid loading unless the function is actually used
    from util.api import get_data
    from concurrent.futures import ThreadPoolExecutor
    import polars as pl

    # Copy options and force API to return polars DataFrames
    api_opts = {**options, "return_polars": True}

    # Extract the symbol once (assumes all rows use the same symbol)
    symbol = df["symbol"].item(0)

    # Extract the timeframe once (same assumption)
    tf = df["timeframe"].item(0)

    # Get the earliest timestamp in the input data
    time_min = df["time_ms"].item(0)

    # Ensure time_ms is an unsigned integer so math works correctly
    ldf = df.lazy().with_columns([pl.col("time_ms").cast(pl.UInt64)])

    def fetch_heartbeat():
        # Fetch the latest BTC-USD 1-minute candle
        # This acts as a global "market is alive" signal
        return get_data(
            symbol="BTC-USD",
            timeframe="1m",
            limit=1,
            order="desc",
            options=api_opts
        )

    def fetch_asset_last():
        # Fetch the latest 1-minute candle for the current asset
        # Starting after the earliest timestamp we care about
        return get_data(
            symbol=symbol,
            timeframe="1m",
            after_ms=time_min,
            limit=1,
            order="desc",
            options=api_opts
        )

    # Run both API calls at the same time to save latency
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_heartbeat = executor.submit(fetch_heartbeat)
        future_asset = executor.submit(fetch_asset_last)

        # Block until both API calls finish and grab the results
        heartbeat_df = future_heartbeat.result()
        ldf_1m = future_asset.result()

    # Latest timestamp from BTC-USD (global clock)
    global_now_ms = heartbeat_df["time_ms"][0]

    # Latest timestamp from the asset being analyzed
    last_ms = ldf_1m["time_ms"][0]

    # Drift
    drift = (global_now_ms - last_ms) / 60000
    
    ldf = ldf.with_columns(
        pl.lit(drift).alias("drift")
    )

    return ldf.select(["drift"])