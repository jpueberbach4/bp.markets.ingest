import polars as pl
import numpy as np
from typing import List, Dict, Any

try:
    import numba
except ImportError:
    raise ImportError("Numba is required. Run 'pip install numba' OR 'pip install -r requirements.txt'")

@numba.jit(nopython=True, cache=True, nogil=True)
def _cybercycle_backend(price: np.ndarray, alpha: float):
    """
    Executes John Ehlers' Cyber Cycle algorithm at C-speed.
    Isolates the cyclic component of price action while eliminating trend distortion.
    """
    n = len(price)
    cycle = np.full(n, np.nan)
    trigger = np.full(n, np.nan)

    if n < 7:
        return cycle, trigger

    smooth = np.zeros(n)
    cyc = np.zeros(n)

    # Calculate Ehlers' 4-bar weighted smoothing to eliminate aliasing noise
    for i in range(3, n):
        smooth[i] = (price[i] + 2.0 * price[i-1] + 2.0 * price[i-2] + price[i-3]) / 6.0

    # Recursive Cyber Cycle calculation
    for i in range(3, n):
        # Ehlers' stabilization phase for the first few bars
        if i < 7:
            cyc[i] = (smooth[i] - 2.0 * smooth[i-1] + smooth[i-2]) / 4.0
        else:
            # The core DSP equation for the Cyber Cycle
            cyc[i] = ((1.0 - 0.5 * alpha)**2) * (smooth[i] - 2.0 * smooth[i-1] + smooth[i-2]) + \
                     2.0 * (1.0 - alpha) * cyc[i-1] - ((1.0 - alpha)**2) * cyc[i-2]

        cycle[i] = cyc[i]
        
        # The trigger line is the cycle delayed by 1 bar
        if i > 0:
            trigger[i] = cyc[i-1]
        else:
            trigger[i] = cyc[i]

    return cycle, trigger
