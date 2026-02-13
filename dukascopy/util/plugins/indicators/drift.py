import polars as pl
from typing import List, Dict, Any

# Import the helper to handle timezone shifts
from util.plugins.indicators.helpers.marketstate_backend import _marketstate_backend_shift_for_symbol

def description() -> str:
    # Return a human-readable explanation of what this indicator does
    return (
        "Drift displays the current drift in minutes relative to the BTC-USD heartbeat symbol, "
        "normalized for timezone differences."
    )

def meta() -> Dict:
    # Metadata used by the platform to identify and validate this indicator
    return {
        "author": "JP",             # Who wrote this
        "version": 1.1,             # Version number (Bumped for TZ fix)
        "panel": 1,                 # UI panel placement
        "verified": 1,              # Marked as verified
        "polars": 0,                # Does not require polars output by default
        "polars_input": 1           # Expects polars input
    }

def warmup_count(options: Dict[str, Any]) -> int:
    return 0

def position_args(args: List[str]) -> Dict[str, Any]:
    return {}

def calculate(df: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    SPECIAL_HANDLING = True
    # Import here to avoid loading unless the function is actually used
    from util.api import get_data
    from concurrent.futures import ThreadPoolExecutor
    import polars as pl

    # Copy options and force API to return polars DataFrames
    api_opts = {**options, "return_polars": True}

    # Extract the symbol once
    symbol = df["symbol"].item(0)

    # Extract the timeframe once
    tf = df["timeframe"].item(0)

    # Get the earliest timestamp in the input data
    time_min = df["time_ms"].item(0)

    # Ensure time_ms is an unsigned integer
    ldf = df.lazy().with_columns([pl.col("time_ms").cast(pl.UInt64)])

    def fetch_heartbeat():
        # Fetch the latest BTC-USD 1-minute candle
        return get_data(
            symbol="BTC-USD",
            timeframe="1m",
            limit=1,
            order="desc",
            options=api_opts
        )

    def fetch_asset_last():
        # Fetch the latest 1-minute candle for the current asset
        # We use 1m here (regardless of chart TF) to get the most granular 'liveness' check
        return get_data(
            symbol=symbol,
            timeframe="1m",
            after_ms=time_min,
            limit=1,
            order="desc",
            options=api_opts
        )

    # Run both API calls at the same time
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_heartbeat = executor.submit(fetch_heartbeat)
        future_asset = executor.submit(fetch_asset_last)

        # Block until both API calls finish
        heartbeat_df = future_heartbeat.result()
        asset_1m_df = future_asset.result()

    # Safety check for empty returns (e.g. fresh install or bad connection)
    if heartbeat_df.is_empty() or asset_1m_df.is_empty():
        return ldf.with_columns(pl.lit(0.0).alias("drift")).select("drift")

    # Latest timestamp from BTC-USD (global clock)
    global_now_ms = heartbeat_df["time_ms"][0]

    # Latest timestamp from the asset being analyzed
    last_ms = asset_1m_df["time_ms"][0]

    drift_ms = 0

    if SPECIAL_HANDLING:
        # Determine the shift applied to BTC (likely NY DST/STD)
        btc_shift = _marketstate_backend_shift_for_symbol("BTC-USD", global_now_ms)
        
        # Determine the shift applied to the Asset (likely UTC or NY)
        asset_shift = _marketstate_backend_shift_for_symbol(symbol, last_ms)

        # Normalize both to absolute UTC
        btc_utc = global_now_ms - btc_shift
        asset_utc = last_ms - asset_shift

        # Calculate TRUE drift in milliseconds
        drift_ms = btc_utc - asset_utc
    else:
        # Standard raw math
        drift_ms = global_now_ms - last_ms

    # Convert milliseconds to minutes
    drift_minutes = drift_ms / 60000.0
    
    # Create the result column
    ldf = ldf.with_columns(
        pl.lit(drift_minutes).alias("drift")
    )

    return ldf.select(["drift"])