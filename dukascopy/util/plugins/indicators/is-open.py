import polars as pl
from typing import List, Dict, Any

def description() -> str:
    # Return a human-readable explanation of what this indicator does
    return (
        "Determines whether each candle is open or closed by comparing it "
        "against the most recent 1-minute candle. The BTC-USD 1-minute market "
        "is used as a continuous 24/7 heartbeat to reliably detect global market activity."
    )

def meta() -> Dict:
    # Metadata used by the platform to identify and validate this indicator
    return {
        "author": "JP",             # Who wrote this
        "version": 2.6,             # Version number
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

    # FAST PATH: 1m candles are always closed in this system
    if tf == "1m":
        return ldf.with_columns(
            pl.lit(0, dtype=pl.Int8).alias("is-open")
        ).select("is-open")

    def fetch_heartbeat_btc():
        # Fetch the latest BTC-USD 1-minute candle
        # This acts as a global "market is alive" signal
        return get_data(
            symbol="BTC-USD",
            timeframe="1m",
            limit=1,
            order="desc",
            options=api_opts
        )

    def fetch_heartbeat_asset():
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
    
    def fetch_heartbeat_asset_tf():
        # Fetch the latest candle for the current asset and timeframe
        return get_data(
            symbol=symbol,
            timeframe=tf,
            limit=1,
            order="desc",
            options=api_opts
        )

    # Run both API calls at the same time to save latency
    with ThreadPoolExecutor(max_workers=3) as executor:
        future_heartbeat_btc = executor.submit(fetch_heartbeat_btc)
        future_heartbeat_asset = executor.submit(fetch_heartbeat_asset)
        future_heartbeat_asset_tf = executor.submit(fetch_heartbeat_asset_tf)


        # Block until both API calls finish and grab the results
        heartbeat_btc_df = future_heartbeat_btc.result()
        heartbeat_asset_df = future_heartbeat_asset.result()
        heartbeat_asset_tf_df = future_heartbeat_asset_tf.result()

    # Latest timestamp from BTC-USD (global clock)
    heartbeat_btc_ms = heartbeat_btc_df["time_ms"][0]

    # Latest timestamp from the asset being analyzed
    heartbeat_asset_ms = heartbeat_asset_df["time_ms"][0]

    # Latest timestamp from the asset and timeframe being analyzed
    heartbeat_asset_tf_ms = heartbeat_asset_tf_df["time_ms"][0]

    # Calculate drift
    drift_ms = heartbeat_btc_ms - heartbeat_asset_ms

    if tf in ["1M", "1Y"]:
        # Special handling for monthly and yearly candles
        from datetime import datetime

        # Convert last candle time into a datetime object
        dt = datetime.fromtimestamp(heartbeat_asset_ms / 1000)

        if tf == "1M":
            # Start of the current month
            mark_ms = int(
                dt.replace(
                    day=1, hour=0, minute=0, second=0, microsecond=0
                ).timestamp() * 1000
            )
        else:
            # Start of the current year
            mark_ms = int(
                dt.replace(
                    month=1, day=1, hour=0, minute=0, second=0, microsecond=0
                ).timestamp() * 1000
            )
    else:
        # Duration (in ms) of each supported timeframe
        tf_lengths = {
            "2m": 120000,
            "3m": 180000,
            "5m": 300000,
            "10m": 600000,
            "15m": 900000,
            "30m": 1800000,
            "1h": 3600000,
            "2h": 7200000,
            "3h": 10800000,
            "4h": 14400000,
            "6h": 21600000,
            "8h": 28800000,
            "12h": 43200000,
            "1d": 86400000,
            "1W": 604800000,
        }

        # Extra handling for candles that may span a bigger period than the tf may 
        # indicate (eg SGD-IDX:1151 merge logic)

        # See configuration of SGD-IDX config/dukascopy/timeframes/indices/SGD-indices.yaml
        if drift_ms < tf_lengths.get(tf, 0) and tf_lengths.get(tf, 0) < 86400000:
            # This is only applicable to timeframes < 1D, just mark the last candle as open
            mark_ms = heartbeat_asset_tf_ms
        else:
            # Regular path, compute the boundary timestamp for the current candle
            mark_ms = heartbeat_btc_ms - tf_lengths.get(tf, 0)

    is_open_expr = (pl.col("time_ms") >= mark_ms).cast(pl.Int8).alias("is_open")

    if tf in ["1M", "1Y"]:
        # Monthly/Yearly candles are ALWAYS open if they are the latest period, 
        # regardless of whether it's the weekend.
        ldf = ldf.with_columns(is_open_expr)
    else:
        # Standard live market check
        ldf = ldf.with_columns(is_open_expr)

    # Return only the is_open column as the final output
    return ldf.select(["is_open"])