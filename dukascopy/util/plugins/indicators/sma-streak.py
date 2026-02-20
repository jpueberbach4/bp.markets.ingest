import polars as pl
from typing import List, Dict, Any

def description() -> str:
    return (
        "Dual SMA-N Structural Counter. Tracks 'Down Streaks' (Lower-Lows) and "
        "'Up Streaks' (Higher-Highs). Downward resets if price breaks above last "
        "Lower-High. Upward resets if price breaks below last Higher-Low.\n\n"
        "Experimental"
    )

def meta() -> Dict:
    return {
        "author": "Gemini",
        "version": 10.0,
        "panel": 1,
        "verified": 1,
        "polars_input": 1
    }

def warmup_count(options: Dict[str, Any]) -> int:
    return int(options.get('sma-period', 5)) * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "sma-period": args[0] if len(args) > 0 else "3",
        "min-spacing": args[1] if len(args) > 1 else "5"
    }

def calculate(df: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    import polars as pl
    import numpy as np

    sma_period = int(options.get('sma-period', 5))
    min_spacing = int(options.get('min-spacing', 5))

    df_raw = df.with_row_count("index").with_columns([
        pl.col("close").rolling_mean(window_size=sma_period).alias("_sma")
    ])
    
    sma = df_raw["_sma"].to_numpy()
    times = df_raw["time_ms"].to_numpy()
    
    down_streaks = [0.0] * len(sma)
    up_streaks = [0.0] * len(sma)
    
    d_streak = 0
    d_last_low = float('inf')
    d_last_idx = -1000
    d_ceiling = float('inf') # The Lower-High
    
    u_streak = 0
    u_last_high = float('-inf')
    u_last_idx = -1000
    u_floor = float('-inf') # The Higher-Low
    
    for i in range(2, len(sma)):
        is_low = (sma[i-1] < sma[i-2]) and (sma[i-1] < sma[i])
        is_high = (sma[i-1] > sma[i-2]) and (sma[i-1] > sma[i])
        
        if sma[i] > d_ceiling:
            d_streak = 0
            d_last_low = float('inf')
        
        if is_high:
            d_ceiling = sma[i-1] # Update the Ceiling for downward trend
            
        if is_low:
            if (i - 1 - d_last_idx) >= min_spacing:
                if sma[i-1] < d_last_low:
                    d_streak += 1
                    d_last_low = sma[i-1]
                else:
                    d_streak = 0 # Higher-Low reset
                    d_last_low = sma[i-1]
                d_last_idx = i - 1
        
        if sma[i] < u_floor:
            u_streak = 0
            u_last_high = float('-inf')
            
        if is_low:
            u_floor = sma[i-1] # Update the Floor for upward trend
            
        if is_high:
            if (i - 1 - u_last_idx) >= min_spacing:
                if sma[i-1] > u_last_high:
                    u_streak += 1
                    u_last_high = sma[i-1]
                else:
                    u_streak = 0 # Lower-High reset
                    u_last_high = sma[i-1]
                u_last_idx = i - 1
        
        down_streaks[i] = float(d_streak)
        up_streaks[i] = float(u_streak)

    return pl.DataFrame({
        "down_streak": down_streaks,
        "up_streak": up_streaks
    })