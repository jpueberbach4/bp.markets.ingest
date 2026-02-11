import numba
import numpy as np

@numba.jit(nopython=True, cache=True, nogil=True)
def _psar_backend(highs: np.ndarray, lows: np.ndarray, step: float, max_step: float) -> np.ndarray:
    """
    Numba-optimized State Machine for PSAR.
    """
    n = len(highs)
    psar = np.zeros(n)
    bull = True 
    af = step
    ep = highs[0]
    psar[0] = lows[0]

    for i in range(1, n):
        prev_psar = psar[i-1]
        
        if bull:
            psar[i] = prev_psar + af * (ep - prev_psar)
            psar[i] = min(psar[i], lows[i-1], lows[max(0, i-2)])
            
            if lows[i] < psar[i]:
                bull = False
                psar[i] = ep
                ep = lows[i]
                af = step
            else:
                if highs[i] > ep:
                    ep = highs[i]
                    af = min(af + step, max_step)
        else:
            psar[i] = prev_psar + af * (ep - prev_psar)
            psar[i] = max(psar[i], highs[i-1], highs[max(0, i-2)])
            
            if highs[i] > psar[i]:
                bull = True
                psar[i] = ep
                ep = highs[i]
                af = step
            else:
                if lows[i] < ep:
                    ep = lows[i]
                    af = min(af + step, max_step)
                    
    return psar