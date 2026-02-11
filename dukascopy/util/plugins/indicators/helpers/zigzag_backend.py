import numba
import numpy as np

@numba.jit(nopython=True, cache=True)
def _zigzag_backend(highs: np.ndarray, lows: np.ndarray, dev_threshold: float) -> np.ndarray:
    n = len(highs)
    pivots = np.full(n, np.nan)
    
    if n < 2:
        return pivots

    trend = 0 
    curr_ext_val = 0.0
    curr_ext_idx = 0
    start_price = highs[0]

    idx_start = 1
    for i in range(1, n):
        if highs[i] > start_price * (1 + dev_threshold):
            trend = 1
            pivots[0] = lows[0]
            curr_ext_val = highs[i]
            curr_ext_idx = i
            idx_start = i + 1
            break
        elif lows[i] < start_price * (1 - dev_threshold):
            trend = -1
            pivots[0] = highs[0]
            curr_ext_val = lows[i]
            curr_ext_idx = i
            idx_start = i + 1
            break
            
    if trend == 0:
        return pivots

    for i in range(idx_start, n):
        if trend == 1: # Uptrend
            if highs[i] > curr_ext_val:
                curr_ext_val = highs[i]
                curr_ext_idx = i
            elif lows[i] < curr_ext_val * (1 - dev_threshold):
                pivots[curr_ext_idx] = curr_ext_val
                trend = -1
                curr_ext_val = lows[i]
                curr_ext_idx = i
        else: # Downtrend
            if lows[i] < curr_ext_val:
                curr_ext_val = lows[i]
                curr_ext_idx = i
            elif highs[i] > curr_ext_val * (1 + dev_threshold):
                pivots[curr_ext_idx] = curr_ext_val
                trend = 1
                curr_ext_val = highs[i]
                curr_ext_idx = i

    pivots[curr_ext_idx] = curr_ext_val
    return pivots