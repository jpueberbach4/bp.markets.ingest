import numpy as np
import numba

@numba.jit(nopython=True, cache=True)
def _cci_backend(tp: np.ndarray, period: int):
    size = tp.shape[0]
    cci = np.full(size, np.nan, dtype=np.float64)
    
    for i in range(period - 1, size):
        window = tp[i - period + 1 : i + 1]
        m = np.mean(window)
        mad = np.mean(np.abs(window - m))
        
        if mad != 0:
            cci[i] = (tp[i] - m) / (0.015 * mad)
        else:
            cci[i] = 0.0
            
    return cci