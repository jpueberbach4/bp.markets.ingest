import numpy as np
import numba

@numba.jit(nopython=True, cache=True)
def _stc_backend(close: np.ndarray, cycle: int, fast: int, slow: int):
    size = len(close)
    stc_out = np.full(size, np.nan, dtype=np.float64)
    
    # 1. EMA logic (Recursive)
    alpha_fast = 2.0 / (fast + 1)
    alpha_slow = 2.0 / (slow + 1)
    smooth_span = max(1, int(cycle / 2))
    alpha_smooth = 2.0 / (smooth_span + 1)

    # State variables for EMAs
    ema_f, ema_s = close[0], close[0]
    
    # Intermediate buffers
    macd = np.zeros(size)
    smooth_1 = np.zeros(size)
    
    # Current smoothing states
    s1_ema = 0.0
    stc_ema = 0.0

    for i in range(size):
        # Update MACD
        ema_f = (close[i] - ema_f) * alpha_fast + ema_f
        ema_s = (close[i] - ema_s) * alpha_slow + ema_s
        macd[i] = ema_f - ema_s

        if i >= cycle:
            # First Stochastic Cycle
            m_win = macd[i - cycle + 1 : i + 1]
            m_min, m_max = np.min(m_win), np.max(m_win)
            denom1 = m_max - m_min
            v1 = 100 * (macd[i] - m_min) / denom1 if denom1 != 0 else 0.0
            s1_ema = (v1 - s1_ema) * alpha_smooth + s1_ema
            smooth_1[i] = s1_ema

            # Second Stochastic Cycle
            if i >= cycle * 2:
                s_win = smooth_1[i - cycle + 1 : i + 1]
                s_min, s_max = np.min(s_win), np.max(s_win)
                denom2 = s_max - s_min
                v2 = 100 * (smooth_1[i] - s_min) / denom2 if denom2 != 0 else 0.0
                stc_ema = (v2 - stc_ema) * alpha_smooth + stc_ema
                stc_out[i] = stc_ema

    return stc_out
