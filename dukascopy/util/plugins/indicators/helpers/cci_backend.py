import numpy as np
import numba

@numba.jit(nopython=True, cache=True, nogil=True)
def _cci_backend(tp: np.ndarray, period: int):
    size = tp.shape[0]
    cci = np.full(size, np.nan, dtype=np.float64)
    
    inv_period = 1.0 / period
    inv_alpha = 1.0 / 0.015
    
    for i in range(period - 1, size):
        window = tp[i - period + 1 : i + 1]
        
        s = 0.0
        for val in window:
            s += val
        m = s * inv_period
        
        m_abs_dev = 0.0
        for val in window:
            m_abs_dev += abs(val - m)
        mad = m_abs_dev * inv_period
        
        if mad > 1e-12:
            cci[i] = (tp[i] - m) * inv_alpha / mad
        else:
            cci[i] = 0.0
            
    return cci