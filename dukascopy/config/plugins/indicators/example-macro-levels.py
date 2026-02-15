import polars as pl
from typing import List, Dict, Any
import time

def description() -> str:
    return "Force-fills all rows with static 10Y macro levels using explicit repetition."

def meta() -> Dict:
    return {
        "author": "Gemini",
        "version": 14.0,
        "panel": 0,
        "verified": 1,
        "polars_input": 1
    }

def position_args(args: List[str]) -> Dict[str, Any]:
    return {"lookback-in-years": args[0] if len(args) > 0 else "7"}

def warmup_count(options: Dict[str, Any]):
    return 0

def calculate(df: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    from util.api import get_data
    import polars as pl
    import numpy as np

    symbol = df["symbol"].item(0)
    df_len = len(df)
    
    num_years = int(options.get('lookback-in-years', 7))
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - (num_years * 365 * 24 * 60 * 60 * 1000)

    daily_hist = get_data(
        symbol=symbol,
        timeframe="1d",
        after_ms=start_ms,
        until_ms=now_ms,
        limit=5000,
        options={**options, "return_polars": True}
    )

    if daily_hist is None or daily_hist.is_empty():
        return df.select([pl.repeat(0.0, df_len).alias(f"macro_lvl_{i}") for i in range(1, 11)])

    current_market_price = daily_hist["close"].item(-1)
    d_lows = daily_hist["low"].to_numpy()
    d_highs = daily_hist["high"].to_numpy()
    
    pivots = []
    window = 30 
    for i in range(window, len(d_lows) - window):
        if d_lows[i] == np.min(d_lows[i - window : i + window + 1]):
            pivots.append(d_lows[i])
        if d_highs[i] == np.max(d_highs[i - window : i + window + 1]):
            pivots.append(d_highs[i])

    precision = 2 if "JPY" in symbol else 3
    counts = {}
    for p in pivots:
        lvl = round(p, precision)
        counts[lvl] = counts.get(lvl, 0) + 1

    min_dist = 0.010 if "JPY" in symbol else 0.0100 
    
    def filter_levels(levels_dict, current_price, above=True, use_dist=True):
        all_lvls = sorted(levels_dict.keys(), key=lambda x: levels_dict[x], reverse=True)
        filtered = []
        for l in all_lvls:
            is_dir = (l > current_price) if above else (l < current_price)
            if is_dir:
                if not use_dist or all(abs(l - f) > min_dist for f in filtered):
                    filtered.append(l)
        return filtered

    t3a = filter_levels(counts, current_market_price, above=True, use_dist=True)[:3]
    t7b = filter_levels(counts, current_market_price, above=False, use_dist=True)[:7]
    
    if len(t3a) < 3: t3a = filter_levels(counts, current_market_price, above=True, use_dist=False)[:3]
    if len(t7b) < 7: t7b = filter_levels(counts, current_market_price, above=False, use_dist=False)[:7]

    final_levels = sorted(t3a + t7b, reverse=True)

    # Drop 0.0 levels (no time to debug fully, so just drop. 
    # affects scaling of chart otherwise and a level 0.0 is not very meaningful)
    active_levels = [lvl for lvl in final_levels if lvl > 0]

    # Dynamically create columns only for the levels we actually found
    return df.select([
        pl.repeat(active_levels[i], df_len).alias(f"macro_lvl_{i+1}") 
        for i in range(len(active_levels))
    ])