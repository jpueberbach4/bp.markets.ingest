import numpy as np
import numba
import math

@numba.jit(nopython=True, cache=True, nogil=True)
def _supersmoother_backend(price: np.ndarray, period: float):
    """2-Pole SuperSmoother Filter."""
    n = len(price)
    filt = np.full(n, np.nan)
    if n < 3: return filt
    
    a1 = math.exp(-1.414 * math.pi / period)
    b1 = 2.0 * a1 * math.cos(1.414 * math.pi / period)
    c2 = b1
    c3 = -a1 * a1
    c1 = 1.0 - c2 - c3
    
    filt[:2] = price[:2]
    for i in range(2, n):
        filt[i] = c1 * (price[i] + price[i-1]) / 2.0 + c2 * filt[i-1] + c3 * filt[i-2]
    return filt