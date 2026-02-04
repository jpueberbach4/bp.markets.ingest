import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    return "Rolling Volume Profile: Calculates POC and Value Area (VAH/VAL) over a moving window."

def meta() -> Dict:
    return {"author": "Google Gemini", "version": 2.0, "panel": 0, "verified": 1, "polars": 0}

def warmup_count(options: Dict[str, Any]) -> int:
    return int(options.get('period', 100))

def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "period": args[0] if len(args) > 0 else "100",
        "ticks": args[1] if len(args) > 1 else "0.5"
    }

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    p = int(options.get('period', 100))
    tick_size = float(options.get('ticks', 0.5))
    
    n = len(df)
    poc_arr = np.full(n, np.nan)
    vah_arr = np.full(n, np.nan)
    val_arr = np.full(n, np.nan)
    
    close = df['close'].values
    volume = df['volume'].values
    lows = df['low'].values
    highs = df['high'].values
    
    for i in range(p, n):
        w_close = close[i-p:i]
        w_vol = volume[i-p:i]
        min_p = np.min(lows[i-p:i])
        max_p = np.max(highs[i-p:i])
        
        bins = np.arange(min_p, max_p + tick_size, tick_size)
        if len(bins) < 2: continue # Not enough price variation
            
        hist, bin_edges = np.histogram(w_close, bins=bins, weights=w_vol)
        
        poc_idx = np.argmax(hist)
        poc_arr[i] = bin_edges[poc_idx]
        
        total_vol = np.sum(hist)
        target_vol = total_vol * 0.70
        
        sorted_indices = np.argsort(hist)[::-1]
        
        current_vol = 0
        va_prices = []
        
        for idx in sorted_indices:
            current_vol += hist[idx]
            va_prices.append(bin_edges[idx])
            if current_vol >= target_vol:
                break
        
        if va_prices:
            vah_arr[i] = np.max(va_prices)
            val_arr[i] = np.min(va_prices)
            
    return pd.DataFrame({
        'poc': poc_arr,
        'vah': vah_arr,
        'val': val_arr
    }, index=df.index)