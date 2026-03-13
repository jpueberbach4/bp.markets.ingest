import polars as pl
import numpy as np
from typing import List, Dict, Any

try:
    import numba
except ImportError:
    raise ImportError("Numba is required. Run 'pip install numba' OR 'pip install -r requirements.txt'")

@numba.jit(nopython=True, cache=True, nogil=True)
def _laguerrersi_backend(price: np.ndarray, gamma: float):
    """
    Executes John Ehlers' Laguerre RSI algorithm at C-speed.
    Uses a 4-element Laguerre filter network to create a zero-lag, ultra-smooth RSI.
    """
    n = len(price)
    rsi = np.full(n, np.nan)

    if n < 2:
        return rsi

    # Initialize the 4 filter poles with the first price to prevent long settling times
    L0 = price[0]
    L1 = price[0]
    L2 = price[0]
    L3 = price[0]

    for i in range(n):
        # Store previous bar's filter states
        L0_prev = L0
        L1_prev = L1
        L2_prev = L2
        L3_prev = L3
        
        # Calculate the Laguerre filter network equations
        L0 = (1.0 - gamma) * price[i] + gamma * L0_prev
        L1 = -gamma * L0 + L0_prev + gamma * L1_prev
        L2 = -gamma * L1 + L1_prev + gamma * L2_prev
        L3 = -gamma * L2 + L2_prev + gamma * L3_prev
        
        CU = 0.0  # Component Up
        CD = 0.0  # Component Down
        
        # Calculate differences between the filter poles
        if L0 >= L1:
            CU += L0 - L1
        else:
            CD += L1 - L0
            
        if L1 >= L2:
            CU += L1 - L2
        else:
            CD += L2 - L1
            
        if L2 >= L3:
            CU += L2 - L3
        else:
            CD += L3 - L2
            
        # Calculate the final bounded RSI value (0 to 1.0)
        if CU + CD != 0.0:
            rsi[i] = CU / (CU + CD)
        else:
            rsi[i] = 0.0
            
    return rsi
