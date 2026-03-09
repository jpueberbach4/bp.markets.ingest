import polars as pl
from typing import List, Dict, Any

def description() -> str:
    return (
        "Major Pivot Identifier. Scans N-bar neighborhood to find structural peaks and bottoms. "
        "Parameter 'what' filters output: 'tops' (1.0), 'bottoms' (-1.0), or 'all' (both). "
        "Warning: this indicator has lookahead bias because of center=True. "
        "Strictly for ML Y-axis targeting."
    )

def meta() -> Dict:
    return {
        "author": "Gemini",
        "version": 3.1,
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
        "what": args[1] if len(args) > 1 else "all"
    }

def calculate(df: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    import polars as pl

    n = int(options.get('window', 50))
    what = str(options.get('what', 'all')).strip().lower()

    # Base calculations for both max and min
    df_lazy = df.lazy().with_columns([
        pl.col("high").rolling_max(window_size=n*2+1, center=True).alias("local_max"),
        pl.col("low").rolling_min(window_size=n*2+1, center=True).alias("local_min")
    ])

    # Dynamic evaluation based on the 'what' parameter
    if what == "tops":
        pivot_expr = (
            pl.when(pl.col("high") == pl.col("local_max"))
            .then(1.0)
            .otherwise(0.0)
        )
    elif what == "bottoms":
        pivot_expr = (
            pl.when(pl.col("low") == pl.col("local_min"))
            .then(-1.0)
            .otherwise(0.0)
        )
    else:  # "all" or any unrecognized string defaults to both
        pivot_expr = (
            pl.when(pl.col("high") == pl.col("local_max"))
            .then(1.0)
            .when(pl.col("low") == pl.col("local_min"))
            .then(-1.0)
            .otherwise(0.0)
        )

    return (
        df_lazy
        .select([
            pivot_expr.alias("major_pivot")
        ])
        .collect(engine="streaming")
    )