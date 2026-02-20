import polars as pl
from typing import List, Dict, Any

def description() -> str:
    return (
        "Consecutive Down-Bars. Counts the number of consecutive candles where "
        "close < close[1]. Resets to 0 on an up-bar. Excellent for identifying "
        "exhaustion and 'V-bottom' contexts without lookahead bias."
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
    # No window needed, but we look back 1 bar
    return 1

def position_args(args: List[str]) -> Dict[str, Any]:
    return {}

def calculate(df: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    import polars as pl

    return (
        df.lazy()
        .with_columns([
            # 1 if price went down, 0 otherwise
            (pl.col("close") < pl.col("close").shift(1))
            .cast(pl.Int32)
            .alias("_is_down")
        ])
        .with_columns([
            # Create unique IDs for setiap streak of identical values
            (pl.col("_is_down") != pl.col("_is_down").shift(1))
            .fill_null(True)
            .cum_sum()
            .alias("_streak_id")
        ])
        .with_columns([
            # Count occurrences within each streak
            pl.struct(["_is_down", "_streak_id"])
            .cum_count()
            .over("_streak_id")
            .alias("_count")
        ])
        .select([
            # Only return the count if the streak is a "Down" streak
            pl.when(pl.col("_is_down") == 1)
            .then(pl.col("_count"))
            .otherwise(0)
            .cast(pl.Float64)
            .alias("consecutive_down")
        ])
        .collect(streaming=True)
    )