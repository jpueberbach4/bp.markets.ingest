import polars as pl
from typing import List, Dict, Any

def description() -> str:
    return (
        "Dual SMA-N Structural Counter. Tracks 'Down Streaks' (LL) and 'Up Streaks' (HH). "
        "Calculates 'structural_bias' as (up_streak - down_streak). "
        "Instant reset on ceiling/floor breaches. Parameterized for GA optimization.\n\n"
        "<b>Experimental</b>"
    )

def meta() -> Dict:
    return {
        "author": "Gemini",
        "version": 10.2,
        "panel": 1,
        "verified": 1,
        "polars_input": 1
    }

def warmup_count(options: Dict[str, Any]) -> int:
    return int(options.get('sma-period', 3)) * 4

def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "sma-period": args[0] if len(args) > 0 else "3",
        "min-spacing": args[1] if len(args) > 1 else "5"
    }

def calculate(df: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    import polars as pl
    import numpy as np

    sma_period = int(options.get('sma-period', 3))
    min_spacing = int(options.get('min-spacing', 5))

    # 1. Prepare smoothed series
    df_raw = df.with_row_count("index").with_columns([
        pl.col("close").rolling_mean(window_size=sma_period).alias("_sma")
    ])
    
    sma = df_raw["_sma"].to_numpy()
    
    down_streaks = np.zeros(len(sma))
    up_streaks = np.zeros(len(sma))
    
    # State variables: Downward (LL)
    d_streak = 0
    d_last_low = float('inf')
    d_last_idx = -1000
    d_ceiling = float('inf') 
    
    # State variables: Upward (HH)
    u_streak = 0
    u_last_high = float('-inf')
    u_last_idx = -1000
    u_floor = float('-inf') 
    
    start_idx = max(2, sma_period)
    
    # State Machine Logic
    for i in range(start_idx, len(sma)):
        is_low = (sma[i-1] < sma[i-2]) and (sma[i-1] < sma[i])
        is_high = (sma[i-1] > sma[i-2]) and (sma[i-1] > sma[i])
        
        # --- DOWNWARD TREND ---
        if sma[i] > d_ceiling:
            d_streak = 0
            d_last_low = float('inf')
        
        if is_high:
            d_ceiling = sma[i-1]
            
        if is_low:
            if (i - 1 - d_last_idx) >= min_spacing:
                if sma[i-1] < d_last_low:
                    d_streak += 1
                else:
                    d_streak = 0
                d_last_low = sma[i-1]
                d_last_idx = i - 1
        
        # --- UPWARD TREND ---
        if sma[i] < u_floor:
            u_streak = 0
            u_last_high = float('-inf')
            
        if is_low:
            u_floor = sma[i-1]
            
        if is_high:
            if (i - 1 - u_last_idx) >= min_spacing:
                if sma[i-1] > u_last_high:
                    u_streak += 1
                else:
                    u_streak = 0
                u_last_high = sma[i-1]
                u_last_idx = i - 1
        
        down_streaks[i] = float(d_streak)
        up_streaks[i] = float(u_streak)

    # Calculate Bias (Up - Down)
    # A positive value means structural uptrend, negative means downtrend.
    structural_bias = up_streaks - down_streaks

    return pl.DataFrame({
        "down": down_streaks,
        "up": up_streaks,
        "bias": structural_bias
    })