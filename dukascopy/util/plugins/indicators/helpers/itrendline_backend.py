import numpy as np

try:
    import numba
except ImportError:
    raise ImportError("Numba is required. Run 'pip install numba'")

@numba.jit(nopython=True, cache=True, nogil=True)
def _itrendline_backend(price: np.ndarray, alpha: float):
    """
    Executes John Ehlers' Instantaneous Trendline (iTrend) algorithm at C-speed.
    Isolates the trend by mathematically subtracting the cyclic components.
    """
    n = len(price)
    it = np.full(n, np.nan)
    trigger = np.full(n, np.nan)
    
    if n < 3: 
        return it, trigger
    
    # Initialize the first two bars to align with price
    it[0] = price[0]
    it[1] = price[1]
    
    for i in range(2, n):
        # Ehlers' Instantaneous Trendline equation
        it[i] = (alpha - (alpha**2) / 4.0) * price[i] + 0.5 * (alpha**2) * price[i-1] \
                - (alpha - 0.75 * (alpha**2)) * price[i-2] \
                + 2.0 * (1.0 - alpha) * it[i-1] - ((1.0 - alpha)**2) * it[i-2]
                
        # The trigger line computes the trend's momentum difference to create a zero-lag crossover
        trigger[i] = 2.0 * it[i] - it[i-2]
        
    return it, trigger