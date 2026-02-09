import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    return "Rolling Market Profile (TPO): Calculates Time-based POC and Value Area over a moving window."

def meta() -> Dict:
    return {"author": "Google Gemini", "version": 2.0, "panel": 0, "verified": 1, "polars": 0, "polars_input": 1}

def warmup_count(options: Dict[str, Any]) -> int:
    return int(options.get('period', 240))

def position_args(args: List[str]) -> Dict[str, Any]:
    return {"period": args[0] if len(args) > 0 else "240", "ticks": args[1] if len(args) > 1 else "1.0"}

def calculate(df: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    """
    Market Profile (TPO) implementation optimized for polars_input: 1.
    Uses Numpy for histogram binning and Value Area (VA) logic.
    """
    try:
        period = int(options.get('period', 240))
        tick_size = float(options.get('ticks', 1.0))
    except (ValueError, TypeError):
        period = 240
        tick_size = 1.0

    n = len(df)

    poc_arr = np.full(n, np.nan)
    vah_arr = np.full(n, np.nan)
    val_arr = np.full(n, np.nan)

    if n < period:
        return pl.DataFrame({
            "tpo_poc": poc_arr,
            "tpo_vah": vah_arr,
            "tpo_val": val_arr
        })

    close = df['close'].to_numpy()
    lows = df['low'].to_numpy()
    highs = df['high'].to_numpy()

    for i in range(period, n):
        start = i - period
        w_close = close[start:i]
        
        min_p = np.min(lows[start:i])
        max_p = np.max(highs[start:i])
        
        bins = np.arange(min_p, max_p + tick_size + 1e-9, tick_size)
        if len(bins) < 2:
            continue
            
        hist, bin_edges = np.histogram(w_close, bins=bins)
        
        poc_idx = np.argmax(hist)
        poc_arr[i] = bin_edges[poc_idx]
        
        total_tpo = np.sum(hist)
        target_tpo = total_tpo * 0.70
        
        sorted_indices = np.argsort(hist)[::-1]
        current_tpo = 0
        va_indices = []
        
        for idx in sorted_indices:
            current_tpo += hist[idx]
            va_indices.append(idx)
            if current_tpo >= target_tpo:
                break
        
        if va_indices:
            va_prices = bin_edges[va_indices]
            vah_arr[i] = np.max(va_prices)
            val_arr[i] = np.min(va_prices)

    return pl.DataFrame({
        'tpo_poc': poc_arr,
        'tpo_vah': vah_arr,
        'tpo_val': val_arr
    })