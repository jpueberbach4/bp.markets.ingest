import numba
import numpy as np

@numba.jit(nopython=True, cache=True)
def _shannonentropy_backend(close_v, period, bins_count):
    n = len(close_v)
    entropy_arr = np.full(n, np.nan)
    efficiency_arr = np.full(n, np.nan)
    
    if n < period:
        return entropy_arr, efficiency_arr

    returns = np.diff(close_v)
    ret_n = len(returns)
    ret_window_size = period - 1
    max_entropy = np.log2(bins_count) if bins_count > 0 else 1.0

    for i in range(ret_window_size, ret_n + 1):
        window = returns[i - ret_window_size : i]
        
        w_min, w_max = np.min(window), np.max(window)
        if w_max == w_min:
            entropy = 0.0
        else:
            bin_width = (w_max - w_min) / bins_count
            counts = np.zeros(bins_count)
            
            for val in window:
                idx = int((val - w_min) / bin_width)
                if idx >= bins_count: idx = bins_count - 1
                counts[idx] += 1
            
            entropy = 0.0
            for c in counts:
                if c > 0:
                    p = c / ret_window_size
                    entropy -= p * np.log2(p)
        
        efficiency = 1.0 - (entropy / max_entropy)
        
        target_idx = i
        entropy_arr[target_idx] = entropy
        efficiency_arr[target_idx] = max(0.0, min(1.0, efficiency))

    return entropy_arr, efficiency_arr