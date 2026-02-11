import numba
import numpy as np

@numba.jit(nopython=True, cache=True)
def _swingpoints_backend(highs: np.ndarray, lows: np.ndarray, left: int, right: int):
    n = len(highs)
    out_high = np.full(n, np.nan, dtype=np.float64)
    out_low = np.full(n, np.nan, dtype=np.float64)
    
    for i in range(left, n - right):
        curr_h = highs[i]
        curr_l = lows[i]
        
        is_high = True
        is_low = True
        
        for j in range(i - left, i + right + 1):
            if highs[j] > curr_h:
                is_high = False
            if lows[j] < curr_l:
                is_low = False
            if not is_high and not is_low:
                break
                
        if is_high:
            out_high[i] = curr_h
        if is_low:
            out_low[i] = curr_l
            
    return out_high, out_low