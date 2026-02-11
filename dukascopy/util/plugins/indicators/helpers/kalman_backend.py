import numba
import numpy as np

@numba.jit(nopython=True, cache=True)
def _kalman_backend(values: np.ndarray, q_val: float, r_val: float) -> np.ndarray:
    size = len(values)
    xhat = np.zeros(size)
    p_val = 1.0
    
    xhat[0] = values[0]
    
    for k in range(1, size):
        p_minus = p_val + q_val
        k_gain = p_minus / (p_minus + r_val)
        xhat[k] = xhat[k-1] + k_gain * (values[k] - xhat[k-1])
        p_val = (1.0 - k_gain) * p_minus
            
    return xhat