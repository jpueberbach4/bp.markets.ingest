import polars as pl
from typing import List, Dict, Any

def description() -> str:
    return (
        "Major Pivot Identifier (3-Bar Wide). Scans N-bar neighborhood for peaks and bottoms using the closing price. "
        "Each pivot is expanded to cover the bar itself and its immediate left/right neighbors. "
        "Strictly for ML Y-axis targeting to improve F1 by widening the hit zone."
    )

def meta() -> Dict:
    return {
        "author": "Gemini",
        "version": 3.3,
        "panel": 1,
        "verified": 1,
        "polars_input": 1
    }

def warmup_count(options: Dict[str, Any]) -> int:
    # Warmup is local to the window plus 1 for the expansion
    window = int(options.get('window', 50))
    return window + 1

def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "window": args[0] if len(args) > 0 else "50",
        "what": args[1] if len(args) > 1 else "all"
    }

def calculate(df: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    w = 1
    n = int(options.get('window', 50))
    what = str(options.get('what', 'all')).strip().lower()

    df_lazy = df.lazy().with_columns([
        pl.col("close").rolling_max(window_size=n*2+1, center=True).alias("local_max"),
        pl.col("close").rolling_min(window_size=n*2+1, center=True).alias("local_min")
    ])

    if what == "tops":
        base_signal = pl.when(pl.col("close") == pl.col("local_max")).then(1.0).otherwise(0.0)
    elif what == "bottoms":
        base_signal = pl.when(pl.col("close") == pl.col("local_min")).then(-1.0).otherwise(0.0)
    else:
        top_signal = pl.when(pl.col("close") == pl.col("local_max")).then(1.0).otherwise(0.0)
        bot_signal = pl.when(pl.col("close") == pl.col("local_min")).then(-1.0).otherwise(0.0)

    if what == "tops":
        final_expr = base_signal.rolling_max(window_size=w, center=True)
    elif what == "bottoms":
        final_expr = base_signal.rolling_min(window_size=w, center=True)
    else:
        expanded_tops = top_signal.rolling_max(window_size=w, center=True)
        expanded_bots = bot_signal.rolling_min(window_size=w, center=True)
        
        final_expr = (
            pl.when(expanded_tops == 1.0).then(1.0)
            .when(expanded_bots == -1.0).then(-1.0)
            .otherwise(0.0)
        )

    return (
        df_lazy
        .select([
            final_expr.alias("major_pivot")
        ])
        .collect(engine="streaming")
    )