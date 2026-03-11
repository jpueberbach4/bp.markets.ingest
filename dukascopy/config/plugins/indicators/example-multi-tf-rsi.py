import polars as pl
from typing import List, Dict, Any

def description() -> str:
    return (
        "Triple RSI Panel: Displays Current, 4H, and 1D RSI in a single panel. "
        "Uses data-relative 'is_open' filtering to prevent repainting on the live-edge.\n"
        "Note: Optionally you can use an other symbol to benchmark against. eg DOLLAR.IDX-USD for EUR-USD.\n"
        "Note: The \"normal-rsi\" is the actual live value. The open-canle value."
    )

def meta() -> Dict:
    return {
        "author": "Google Gemini",
        "version": 2.7, 
        "panel": 1,
        "verified": 1,
        "polars": 0,
        "polars_input": 1,
        "nocheck":1
    }

def warmup_count(options: Dict[str, Any]) -> int:
    # we dont need warmup. its handled upstream
    return 0

def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "benchmark": args[0] if len(args) > 0 else "{symbol}",
        "period": args[1] if len(args) > 1 else "14",
        "period-4h": args[2] if len(args) > 2 else "14",
        "period-1d": args[3] if len(args) > 3 else "14",
        "period-1W": args[4] if len(args) > 4 else "14",
    }

def calculate(df: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    # Import here so these only load when the function actually runs
    from util.api import get_data
    from concurrent.futures import ThreadPoolExecutor
    import polars as pl

    # Toggle for performance profiling (leave False in production)
    profiling_enabled = False
    if profiling_enabled:
        import cProfile, pstats, io
        pr = cProfile.Profile()
        pr.enable()

    symbol = options.get("benchmark", "DOLLAR.IDX-USD")
    # Read RSI period from options, defaulting to 14 if not provided
    rsi_period = int(options.get("period", 14))
    rsi_period_4h = int(options.get("period-4h", 14))
    rsi_period_1d = int(options.get("period-1d", 14))
    rsi_period_1W = int(options.get("period-1W", 14))

    # Build the column name used by the indicator API (e.g. "rsi_14")
    rsi_col = f"rsi_{rsi_period}"
    rsi_col_4h = f"rsi_{rsi_period_4h}"
    rsi_col_1d = f"rsi_{rsi_period_1d}"
    rsi_col_1W = f"rsi_{rsi_period_1W}"

    # Extract static metadata (assumed constant across all rows)
    tf = df["timeframe"].item(0)

    # Determine the time range we need indicator data for
    # Changed this from O(N) (min(),max()) to O(1) operation.
    # On big chunks we don't want O(N) operations, anywhere.
    # When developing indicators, always ask yourself the question:
    # Is this an O(N) operation? Can it be replaced with a O(log N) 
    # or O(1) operation? Especially for ML important!
    # Incoming df's to calculate are always guaranteed to be asc on 
    # time_ms. No scans needed.
    time_min = df["time_ms"][0]
    time_max = df["time_ms"][-1]

    # Force API to return Polars DataFrames
    api_opts = {**options, "return_polars": True}

    warmup_ms = 86400000 * 15 # cover weekends + safety value

    def fetch_indicator_data(target_tf, alias, rsi_ind):
        # Fetch RSI + is-open flags for a given timeframe
        data = get_data(
            symbol=symbol,
            timeframe=target_tf,
            after_ms=time_min - warmup_ms,
            until_ms=time_max + 1,
            indicators=[rsi_ind, "is-open"],
            limit=1000000,
            options=api_opts
        )

        if data.is_empty():
            return pl.DataFrame({
                "time_ms": pl.Series([], dtype=pl.UInt64),
                alias: pl.Series([], dtype=pl.Float64)
            }).lazy()

        # Convert to lazy mode for efficient joins
        # Drop open candles so values only update on closed bars
        # Rename the RSI column so multiple timeframes can coexist
        return (
            data.lazy()
            .filter(pl.col("is-open") == 0)
            .select([
                pl.col("time_ms").cast(pl.UInt64),
                pl.col(rsi_ind).alias(alias)  # FIX: Uses local rsi_ind argument instead of outer scope rsi_col
            ])
            .sort("time_ms")
        )

    # Fetch RSI data for three timeframes in parallel to save time
    with ThreadPoolExecutor(max_workers=4) as executor:
        f_current = executor.submit(fetch_indicator_data, tf, "rsi", rsi_col)
        f_4h = executor.submit(fetch_indicator_data, "4h", "rsi4h", rsi_col_4h)
        f_1d = executor.submit(fetch_indicator_data, "1d", "rsi1d", rsi_col_1d)
        f_1W = executor.submit(fetch_indicator_data, "1W", "rsi1W", rsi_col_1W)

        # Wait for all fetches to finish
        lazy_current = f_current.result()
        lazy_4h = f_4h.result()
        lazy_1d = f_1d.result()
        lazy_1W = f_1W.result()

    # Make a flat timeline to join into
    timeline = df.select([pl.col("time_ms").cast(pl.UInt64)]).lazy()
    # Join all RSI streams onto the base timeline
    # Backward as-of join means "use the last known closed value"
    result_ldf = (
        timeline
        .join_asof(lazy_current, on="time_ms", strategy="backward")
        .join_asof(lazy_4h, on="time_ms", strategy="backward")
        .join_asof(lazy_1d, on="time_ms", strategy="backward")
        .join_asof(lazy_1W, on="time_ms", strategy="backward")
        .select(["rsi", "rsi4h", "rsi1d", "rsi1W"])
        .collect(engine="streaming")
    )

    # Stop profiling and print results if enabled
    if profiling_enabled:
        pr.disable()
        s = io.StringIO()
        ps = pstats.Stats(pr, stream=s).sort_stats("cumulative")
        ps.print_stats(20)
        print(s.getvalue())

    # Return the final DataFrame with one RSI per timeframe
    return result_ldf