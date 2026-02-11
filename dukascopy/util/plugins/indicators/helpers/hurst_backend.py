# File: util/hurst_backend.py
import numba
import numpy as np

@numba.jit(nopython=True, cache=True)
def _hurst_backend(close_v: np.ndarray, period: int) -> np.ndarray:
    n = len(close_v)
    hurst_arr = np.full(n, np.nan)
    
    if n < period:
        return hurst_arr

    lags = np.unique(np.linspace(2, period // 2, 5).astype(np.int32))
    num_lags = len(lags)
    log_lags = np.log(lags.astype(np.float64))
    x_mean = np.mean(log_lags)
    x_diff = log_lags - x_mean
    denominator = np.sum(x_diff**2)

    for i in range(period - 1, n):
        window = close_v[i - (period - 1) : i + 1]
        log_taus = np.zeros(num_lags)
        
        for idx in range(num_lags):
            lag = lags[idx]
            diffs = window[lag:] - window[:-lag]
            
            std_val = np.std(diffs)
            if std_val < 1e-10: 
                std_val = 1e-10
            log_taus[idx] = np.log(std_val)
        
        y_mean = np.mean(log_taus)
        numerator = np.sum(x_diff * (log_taus - y_mean))
        
        hurst_arr[i] = (numerator / denominator) * 2.0

    return hurst_arr