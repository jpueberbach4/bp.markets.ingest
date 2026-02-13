import numpy as np
import numba

@numba.jit(nopython=True, cache=True, nogil=True)
def _aroon_backend_up(high: np.ndarray, period: int) -> np.ndarray:
    size = high.shape[0]
    out = np.full(size, np.nan, dtype=np.float64)
    for i in range(period, size):
        window = high[i - period : i + 1]
        # Days since period high
        days_since = period - np.argmax(window)
        out[i] = ((period - days_since) / period) * 100
    return out

@numba.jit(nopython=True, cache=True, nogil=True)
def _aroon_backend_down(low: np.ndarray, period: int) -> np.ndarray:
    size = low.shape[0]
    out = np.full(size, np.nan, dtype=np.float64)
    for i in range(period, size):
        window = low[i - period : i + 1]
        # Days since period low
        days_since = period - np.argmin(window)
        out[i] = ((period - days_since) / period) * 100
    return out