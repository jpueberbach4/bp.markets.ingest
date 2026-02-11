import numba
import numpy as np

@numba.jit(nopython=True, cache=True, nogil=True)
def _mcginley_backend(prices: np.ndarray, period: int) -> np.ndarray:
    n = len(prices)
    md = np.zeros(n)
    
    if n == 0:
        return md
        
    md[0] = prices[0]
    
    for i in range(1, n):
        prev_md = md[i-1]
        price = prices[i]
        
        if prev_md <= 0:
            md[i] = price
        else:
            ratio = price / prev_md
            denominator = period * (ratio ** 4)
            
            if denominator == 0:
                md[i] = price
            else:
                md[i] = prev_md + (price - prev_md) / denominator
                
    return md