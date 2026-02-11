# File: util/mp_backend.py
import numba
import numpy as np

@numba.jit(nopython=True, cache=True)
def _marketprofile_backend(highs, lows, closes, period, tick_size):
    n = len(closes)
    poc_arr = np.full(n, np.nan)
    vah_arr = np.full(n, np.nan)
    val_arr = np.full(n, np.nan)
    
    for i in range(period, n):
        start = i - period
        w_close = closes[start:i]
        min_p = np.min(lows[start:i])
        max_p = np.max(highs[start:i])
        
        num_bins = int(np.ceil((max_p - min_p) / tick_size)) + 1
        if num_bins < 2:
            continue
            
        hist = np.zeros(num_bins, dtype=np.int32)
        bin_edges = np.zeros(num_bins)
        for b in range(num_bins):
            bin_edges[b] = min_p + (b * tick_size)

        for j in range(period):
            bin_idx = int((w_close[j] - min_p) / tick_size)
            if 0 <= bin_idx < num_bins:
                hist[bin_idx] += 1
        
        poc_idx = np.argmax(hist)
        poc_arr[i] = bin_edges[poc_idx]
        
        total_tpo = np.sum(hist)
        target_tpo = total_tpo * 0.70
        sorted_indices = np.argsort(hist)[::-1]
        
        current_tpo = 0
        v_min = np.inf
        v_max = -np.inf
        found_va = False

        for idx in sorted_indices:
            current_tpo += hist[idx]
            price = bin_edges[idx]
            if price < v_min: v_min = price
            if price > v_max: v_max = price
            if current_tpo >= target_tpo:
                found_va = True
                break
        
        if found_va:
            vah_arr[i] = v_max
            val_arr[i] = v_min
            
    return poc_arr, vah_arr, val_arr