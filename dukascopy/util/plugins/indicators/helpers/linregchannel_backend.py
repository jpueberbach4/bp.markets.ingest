import numba
import numpy as np

@numba.jit(nopython=True, cache=True, nogil=True)
def _linregchannel_backend(y: np.ndarray, period: int):
    size = len(y)
    mid_out = np.full(size, np.nan, dtype=np.float64)
    upper_out = np.full(size, np.nan, dtype=np.float64)
    lower_out = np.full(size, np.nan, dtype=np.float64)

    x = np.arange(period, dtype=np.float64)
    x_mean = (period - 1) / 2.0
    x_ss = np.sum((x - x_mean)**2)

    for i in range(period - 1, size):
        window = y[i - period + 1 : i + 1]
        y_mean = np.mean(window)
        
        numerator = 0.0
        for j in range(period):
            numerator += (x[j] - x_mean) * (window[j] - y_mean)
        
        slope = numerator / x_ss
        intercept = y_mean - slope * x_mean
        
        current_mid = slope * (period - 1) + intercept
        
        max_dev = 0.0
        for j in range(period):
            line_val = slope * j + intercept
            dev = abs(window[j] - line_val)
            if dev > max_dev:
                max_dev = dev
        
        mid_out[i] = current_mid
        upper_out[i] = current_mid + max_dev
        lower_out[i] = current_mid - max_dev

    return mid_out, upper_out, lower_out