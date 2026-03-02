import numpy as np
import numba

@numba.jit(nopython=True, cache=True, nogil=True)
def _mom_backend(close: np.ndarray, period: int) -> np.ndarray:
    """
    TA-Lib exact match for Classic Momentum (MOM).
    Calculates the absolute change in price over a specific period.
    Formula: MOM = Close_today - Close_(today - period)
    """
    n = len(close)
    out = np.full(n, np.nan)
    
    # We need at least 'period + 1' bars to calculate a single MOM value
    if period < 1 or n <= period:
        return out
        
    for i in range(period, n):
        out[i] = close[i] - close[i - period]
        
    return out