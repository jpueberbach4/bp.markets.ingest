import numba
import numpy as np

@numba.jit(nopython=True, cache=True)
def _supertrend_backend(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int, multiplier: float) -> np.ndarray:
    n = len(close)
    
    tr = np.zeros(n)
    tr[0] = high[0] - low[0]
    
    for i in range(1, n):
        hl = high[i] - low[i]
        hc = abs(high[i] - close[i-1])
        lc = abs(low[i] - close[i-1])
        if hl > hc and hl > lc:
            tr[i] = hl
        elif hc > lc:
            tr[i] = hc
        else:
            tr[i] = lc

    atr = np.zeros(n)
    if n >= period:
        current_sum = 0.0
        for i in range(period):
            current_sum += tr[i]
        atr[period-1] = current_sum / period
        for i in range(period, n):
            current_sum += tr[i] - tr[i-period]
            atr[i] = current_sum / period

    basic_upper = np.zeros(n)
    basic_lower = np.zeros(n)
    
    for i in range(n):
        hl2 = (high[i] + low[i]) / 2
        basic_upper[i] = hl2 + (multiplier * atr[i])
        basic_lower[i] = hl2 - (multiplier * atr[i])

    final_upper = np.zeros(n)
    final_lower = np.zeros(n)
    supertrend = np.zeros(n)
    trend = 1
    
    final_upper[0] = basic_upper[0]
    final_lower[0] = basic_lower[0]
    supertrend[0] = final_lower[0]
    
    for i in range(1, n):
        if basic_upper[i] < final_upper[i-1] or close[i-1] > final_upper[i-1]:
            final_upper[i] = basic_upper[i]
        else:
            final_upper[i] = final_upper[i-1]
        
        if basic_lower[i] > final_lower[i-1] or close[i-1] < final_lower[i-1]:
            final_lower[i] = basic_lower[i]
        else:
            final_lower[i] = final_lower[i-1]
        
        if trend == 1:
            if close[i] < final_lower[i]:
                trend = -1
                supertrend[i] = final_upper[i]
            else:
                supertrend[i] = final_lower[i]
        else:
            if close[i] > final_upper[i]:
                trend = 1
                supertrend[i] = final_lower[i]
            else:
                supertrend[i] = final_upper[i]
                
    return supertrend