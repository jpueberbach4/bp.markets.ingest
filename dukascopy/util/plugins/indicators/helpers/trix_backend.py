import numba
import numpy as np

@numba.jit(nopython=True, cache=True, nogil=True)
def _trix_backend(close: np.ndarray, period: int) -> np.ndarray:
    n = len(close)
    out = np.full(n, np.nan)
    if period < 1 or n < (3 * period - 2):
        return out
        
    alpha = 2.0 / (period + 1.0)
    
    # 1st EMA
    ema1 = np.full(n, np.nan)
    sum1 = 0.0
    for i in range(period):
        sum1 += close[i]
    ema1[period - 1] = sum1 / period
    for i in range(period, n):
        ema1[i] = (close[i] - ema1[i-1]) * alpha + ema1[i-1]
        
    # 2nd EMA
    ema2 = np.full(n, np.nan)
    sum2 = 0.0
    start2 = period - 1
    for i in range(start2, start2 + period):
        sum2 += ema1[i]
    ema2[start2 + period - 1] = sum2 / period
    for i in range(start2 + period, n):
        ema2[i] = (ema1[i] - ema2[i-1]) * alpha + ema2[i-1]
        
    # 3rd EMA
    ema3 = np.full(n, np.nan)
    sum3 = 0.0
    start3 = start2 + period - 1
    for i in range(start3, start3 + period):
        sum3 += ema2[i]
    ema3[start3 + period - 1] = sum3 / period
    for i in range(start3 + period, n):
        ema3[i] = (ema2[i] - ema3[i-1]) * alpha + ema3[i-1]
        
    # TRIX (Percentage Rate of Change of the 3rd EMA)
    for i in range(start3 + 1, n):
        prev = ema3[i-1]
        if prev != 0.0:
            out[i] = ((ema3[i] - prev) / prev) * 100.0
        else:
            out[i] = 0.0
            
    return out