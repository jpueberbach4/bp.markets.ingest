import polars as pl
from typing import List, Dict, Any

def description() -> str:
    return (
        "Major Pivot Identifier. Scans 1,500 rows to find structural peaks and bottoms. "
        "Marks points that are the absolute high/low within a N-bar neighborhood. "
        "Returns 1.0 for Major Peaks, -1.0 for Major Bottoms, and 0.0 otherwise.\n\n"
        "Warning: this indicator has lookahead bias because of center=True. The indicator "
        "is mainly used for ML purposes. To identify the Y-axis."
    )

def meta() -> Dict:
    return {
        "author": "Gemini",
        "version": 3.0,
        "panel": 1,
        "verified": 1,
        "polars_input": 1
    }

def warmup_count(options: Dict[str, Any]) -> int:
    window = int(options.get('window', 50))
    return window

def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "window": args[0] if len(args) > 0 else "50",
    }

def calculate(df: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    import polars as pl

    n = int(options.get('window', 50))

    return (
        df.lazy()
        .with_columns([
            pl.col("high").rolling_max(window_size=n*2+1, center=True).alias("local_max"),
            pl.col("low").rolling_min(window_size=n*2+1, center=True).alias("local_min")
        ])
        .select([
            pl.when(pl.col("high") == pl.col("local_max"))
            .then(1.0)
            .when(pl.col("low") == pl.col("local_min"))
            .then(-1.0)
            .otherwise(0.0)
            .alias("major_pivot")
        ])
        .collect(streaming=True)
    )