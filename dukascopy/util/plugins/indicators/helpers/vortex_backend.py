import numpy as np
try:
    import numba
except ImportError:
    raise ImportError("Numba is required. Run 'pip install numba' OR 'pip install -r requirements.txt'")

@numba.jit(nopython=True, cache=True, nogil=True)
def _vortex_backend(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int, return_plus: bool) -> np.ndarray:
    """
    Numba-optimized backend for the Vortex Indicator.
    Calculates both +VI and -VI in a single pass using a rolling sum, 
    and returns the requested array based on the `return_plus` flag.
    """
    n = len(close)
    out = np.full(n, np.nan)
    
    # We need at least 'period' bars plus 1 for the initial lookback
    if period < 2 or n < period + 1:
        return out
        
    tr = np.zeros(n)
    pvm = np.zeros(n)
    mvm = np.zeros(n)
    
    # 1. Calculate True Range (TR) and Trend Movements (+VM, -VM) for each bar
    for i in range(1, n):
        hl = high[i] - low[i]
        hc = abs(high[i] - close[i-1])
        lc = abs(low[i] - close[i-1])
        tr[i] = max(hl, max(hc, lc))
        
        pvm[i] = abs(high[i] - low[i-1])
        mvm[i] = abs(low[i] - high[i-1])
        
    pvi = np.full(n, np.nan)
    mvi = np.full(n, np.nan)
    
    sum_tr = 0.0
    sum_pvm = 0.0
    sum_mvm = 0.0
    
    # 2. Initial sum for the first 'period - 1' bars
    for i in range(1, period):
        sum_tr += tr[i]
        sum_pvm += pvm[i]
        sum_mvm += mvm[i]
        
    # 3. Rolling sum for the rest of the array (O(N) efficiency)
    for i in range(period, n):
        sum_tr += tr[i]
        sum_pvm += pvm[i]
        sum_mvm += mvm[i]
        
        if sum_tr != 0.0:
            pvi[i] = sum_pvm / sum_tr
            mvi[i] = sum_mvm / sum_tr
        else:
            pvi[i] = 0.0
            mvi[i] = 0.0
            
        # Remove the oldest value as the window rolls forward
        sum_tr -= tr[i - period + 1]
        sum_pvm -= pvm[i - period + 1]
        sum_mvm -= mvm[i - period + 1]
        
    if return_plus:
        return pvi
    else:
        return mvi