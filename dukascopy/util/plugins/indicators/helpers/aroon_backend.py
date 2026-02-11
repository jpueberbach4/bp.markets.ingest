import numpy as np
import numba

@numba.jit(nopython=True, cache=True)
def _aroon_backend(highs: np.ndarray, lows: np.ndarray, period: int):
    """
    Compiled Numba backend for Aroon.
    """
    size = highs.shape[0]
    out_up = np.full(size, np.nan, dtype=np.float64)
    out_down = np.full(size, np.nan, dtype=np.float64)
    
    window_size = period + 1
    
    for i in range(window_size - 1, size):
        h_win = highs[i - window_size + 1 : i + 1]
        l_win = lows[i - window_size + 1 : i + 1]
        
        out_up[i] = (np.argmax(h_win) / period) * 100
        out_down[i] = (np.argmin(l_win) / period) * 100
        
    return out_up, out_down