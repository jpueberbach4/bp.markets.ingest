import polars as pl
from typing import List, Dict, Any
import time

def description() -> str:
    return (
        "10-Year High-Power Macro Levels. Filters for structural pivots with high touch frequency "
        "and enforces a minimum distance between lines to ensure only distinct major levels are shown."
    )

def meta() -> Dict:
    return {
        "author": "Gemini",
        "version": 11.0,
        "panel": 0,
        "verified": 1,
        "polars_input": 1
    }

def calculate(df: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    from util.api import get_data
    import polars as pl
    import numpy as np

    symbol = df["symbol"].item(0)
    
    # Define 10-year window
    ten_years_ms = 10 * 365 * 24 * 60 * 60 * 1000
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - ten_years_ms

    daily_hist = get_data(
        symbol=symbol,
        timeframe="1d",
        after_ms=start_ms,
        until_ms=now_ms,
        limit=5000,
        options={**options, "return_polars": True}
    )

    if daily_hist.is_empty():
        return df.lazy().select([pl.lit(0.0).alias(f"lvl_{i}") for i in range(1, 11)]).collect()

    current_market_price = daily_hist["close"].item(-1)

    # Extract Macro Pivots
    d_lows = daily_hist["low"].to_numpy()
    d_highs = daily_hist["high"].to_numpy()
    pivots = []
    window = 30 # Looking for monthly extremes
    
    for i in range(window, len(d_lows) - window):
        if d_lows[i] == np.min(d_lows[i - window : i + window + 1]):
            pivots.append(d_lows[i])
        if d_highs[i] == np.max(d_highs[i - window : i + window + 1]):
            pivots.append(d_highs[i])

    # Cluster by Power (Frequency)
    precision = 2 if "JPY" in symbol else 3
    counts = {}
    for p in pivots:
        lvl = round(p, precision)
        counts[lvl] = counts.get(lvl, 0) + 1

    # Spacing Filter (Minimum Distance Logic)
    # We want levels to be at least 100 pips apart for 'Major' status
    min_dist = 0.010 if "JPY" in symbol else 0.0100 
    
    def filter_by_power_and_distance(levels_dict, current_price, above=True):
        # Sort levels by touch frequency (Power)
        all_lvls = sorted(levels_dict.keys(), key=lambda x: levels_dict[x], reverse=True)
        filtered = []
        
        for l in all_lvls:
            if (above and l > current_price) or (not above and l < current_price):
                # Only add if it's far enough from existing filtered levels
                if all(abs(l - f) > min_dist for f in filtered):
                    filtered.append(l)
        return filtered

    # Get 3 above and 7 below
    top_3_above = filter_by_power_and_distance(counts, current_market_price, above=True)[:3]
    top_7_below = filter_by_power_and_distance(counts, current_market_price, above=False)[:7]

    final_levels = sorted(top_3_above + top_7_below, reverse=True)

    while len(final_levels) < 10:
        final_levels.append(0.0)

    # Final Projection
    return (
        df.lazy()
        .select([
            pl.lit(final_levels[i]).alias(f"macro_lvl_{i+1}") 
            for i in range(10)
        ])
        .collect(streaming=True)
    )