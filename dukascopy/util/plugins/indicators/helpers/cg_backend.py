import polars as pl
import numpy as np
from typing import List, Dict, Any

try:
    import numba
except ImportError:
    raise ImportError("Numba is required. Run 'pip install numba' OR 'pip install -r requirements.txt'")

@numba.jit(nopython=True, cache=True, nogil=True)
def _cg_backend(price: np.ndarray, period: int):
    """
    Executes John Ehlers' Center of Gravity (CG) algorithm at C-speed.
    Calculates the weighted center of balance of the price array over the lookback period.
    """
    n = len(price)
    cg = np.full(n, np.nan)
    trigger = np.full(n, np.nan)

    if n < period:
        return cg, trigger

    for i in range(period - 1, n):
        num = 0.0
        denom = 0.0
        
        for j in range(period):
            weight = j + 1.0
            val = price[i - j]
            num += weight * val
            denom += val
        
        if denom != 0.0:
            cg[i] = -num / denom
        else:
            cg[i] = 0.0
            
        if i > 0:
            trigger[i] = cg[i - 1]
        else:
            trigger[i] = cg[i]

    return cg, trigger

