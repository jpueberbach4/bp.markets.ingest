import numpy as np
import numba
try:
    import numba
except ImportError:
    raise ImportError("Numba is required. Run 'pip install numba' OR 'pip install -r requirements.txt'")

@numba.jit(nopython=True, cache=True, nogil=True)
def _cmf_backend(high: np.ndarray, low: np.ndarray, close: np.ndarray, volume: np.ndarray, period: int) -> np.ndarray:
    """
    TA-Lib style exact match for Chaikin Money Flow (CMF).
    Calculates the Money Flow Multiplier, multiplies by Volume to get Money Flow Volume,
    and then takes the ratio of the rolling sum of MFV to the rolling sum of Volume.
    """
    n = len(close)
    out = np.full(n, np.nan)
    
    if period < 1 or n < period:
        return out
        
    mfv = np.zeros(n)
    
    # Calculate Money Flow Volume (MFV) for each bar
    for i in range(n):
        hl_diff = high[i] - low[i]
        if hl_diff != 0.0:
            # Money Flow Multiplier
            mfm = ((close[i] - low[i]) - (high[i] - close[i])) / hl_diff
        else:
            mfm = 0.0
            
        mfv[i] = mfm * volume[i]
        
    # Calculate CMF over the rolling window
    for i in range(period - 1, n):
        sum_mfv = 0.0
        sum_vol = 0.0
        
        # Lookback period accumulation
        for j in range(period):
            sum_mfv += mfv[i - j]
            sum_vol += volume[i - j]
            
        if sum_vol != 0.0:
            out[i] = sum_mfv / sum_vol
        else:
            out[i] = 0.0
            
    return out
