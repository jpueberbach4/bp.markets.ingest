import polars as pl
from typing import List, Dict, Any
import time

def description() -> str:
    return (
        "Major Swing Level Projector. Queries 'example-pivot-finder' on Daily data, "
        "clusters nearby levels to reduce noise, and projects them as static horizontal lines."
        "This example is to demonstrate how to use an other indicators output."
    )

def meta() -> Dict:
    return {
        "author": "Gemini",
        "version": 2.0,
        "panel": 0, # Overlay on main chart
        "verified": 1,
        "polars_input": 1
    }

def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "window": args[0] if len(args) > 0 else "20",
        "lookback-years": args[1] if len(args) > 1 else "2",
        "group-dist-pct": args[2] if len(args) > 2 else "0.10", # Group levels within 0.1%
        "swing-tf": args[3] if len(args) > 3 else "1d",
    }

def warmup_count(options: Dict[str, Any]):
    return 0

def calculate(df: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    from util.api import get_data
    import polars as pl

    symbol = df["symbol"].item(0)
    df_len = len(df)
    
    window = int(options.get("window", 20))
    years = float(options.get("lookback-years", 2))
    group_threshold = float(options.get("group-dist-pct", 0.10)) / 100.0

    tf = options.get("swing-tf", "1d")
    
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - int(years * 365 * 24 * 60 * 60 * 1000)

    pivot_indicator_name = f"example-pivot-finder_{window}"

    pivot_data = get_data(
        symbol=symbol,
        timeframe=tf,
        after_ms=start_ms,
        limit=5000, 
        indicators=[pivot_indicator_name],
        options={**options, "return_polars": True}
    )

    pivot_levels = []

    if pivot_data is not None and not pivot_data.is_empty():
        pivot_cols = [c for c in pivot_data.columns if pivot_indicator_name in c]
        
        if pivot_cols:
            pivot_col_name = pivot_cols[0]
            
            pivots_found = (
                pivot_data.lazy()
                .filter(pl.col(pivot_col_name).abs() == 1.0)
                .select(pl.col("close"))
                .collect()
            )
            
            levels_set = set(pivots_found["close"].to_list())
            pivot_levels = sorted(list(levels_set))

    final_levels = []
    
    if pivot_levels:
        current_group = [pivot_levels[0]]
        
        for i in range(1, len(pivot_levels)):
            lvl = pivot_levels[i]
            prev_lvl = current_group[-1]
            
            dist_pct = (lvl - prev_lvl) / prev_lvl
            
            if dist_pct <= group_threshold:
                current_group.append(lvl)
            else:
                avg_val = sum(current_group) / len(current_group)
                final_levels.append(avg_val)
                current_group = [lvl]
        
        if current_group:
            avg_val = sum(current_group) / len(current_group)
            final_levels.append(avg_val)

    final_levels = sorted(final_levels, reverse=True)

    max_levels = 10
    display_levels = final_levels[:max_levels]
    
    while len(display_levels) < max_levels:
        display_levels.append(None)

    return df.select([
        pl.repeat(lvl, df_len).alias(f"swing_lvl_{i+1}") 
        for i, lvl in enumerate(display_levels)
    ])