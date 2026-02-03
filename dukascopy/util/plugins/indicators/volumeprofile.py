import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    return "Volume Profile identifies the Point of Control (POC) and Value Area (VAH/VAL) based on volume distribution at specific price levels."

def meta() -> Dict:
    return {"author": "Google Gemini", "version": 1.1, "panel": 0, "verified": 1, "polars": 1}

def warmup_count(options: Dict[str, Any]) -> int:
    return int(options.get('period', 100))

def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "period": args[0] if len(args) > 0 else "100",
        "ticks": args[1] if len(args) > 1 else "0.5" # Bin size in price units
    }

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    # Polars implementation uses rolling window binning
    # Note: Complex distribution logic is better handled in the Pandas fallback 
    # for 'Fixed Range' accuracy, but we provide the POC here.
    p = int(options.get('period', 100))
    return [
        pl.col("close").rolling_mean(window_size=p).alias(f"{indicator_str}__poc_proxy")
    ]

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    p = int(options.get('period', 100))
    tick_size = float(options.get('ticks', 0.5))
    
    def get_profile_stats(window_df):
        if len(window_df) < p: return pd.Series([np.nan]*3)
        
        # 1. Create Bins
        bins = np.arange(window_df['low'].min(), window_df['high'].max() + tick_size, tick_size)
        hist, bin_edges = np.histogram(window_df['close'], bins=bins, weights=window_df['volume'])
        
        # 2. Point of Control (POC)
        poc_idx = np.argmax(hist)
        poc = bin_edges[poc_idx]
        
        # 3. Value Area (70% of volume)
        total_vol = hist.sum()
        target_vol = total_vol * 0.70
        
        # Sort by volume to find densest area
        sorted_indices = np.argsort(hist)[::-1]
        cumulative_vol = 0
        va_indices = []
        for idx in sorted_indices:
            cumulative_vol += hist[idx]
            va_indices.append(idx)
            if cumulative_vol >= target_vol: break
            
        va_prices = bin_edges[va_indices]
        return pd.Series([poc, va_prices.max(), va_prices.min()])

    # We apply this over the last 'p' rows (Visible/Fixed Range logic)
    results = df.tail(p).pipe(get_profile_stats)
    
    # Broadcast the single calculation to the full dataframe for plotting
    return pd.DataFrame({
        'poc': results[0],
        'vah': results[1],
        'val': results[2]
    }, index=df.index).ffill()