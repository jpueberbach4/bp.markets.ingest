import numpy as np

try:
    import numba
except ImportError:
    raise ImportError("Numba is required. Run 'pip install numba' OR 'pip install -r requirements.txt'")

@numba.jit(nopython=True, cache=True, nogil=True)
def _fishertransfrom_backend(price: np.ndarray, period: int):
    """
    Executes John Ehlers' Fisher Transform algorithm at C-speed.
    Applies the recursive Normal/Gaussian distribution transform to price action.
    """
    n = len(price)
    fisher = np.full(n, np.nan)
    trigger = np.full(n, np.nan)

    if n < period:
        return fisher, trigger

    value1 = 0.0
    fish = 0.0
    fish_prev = 0.0

    for i in range(period - 1, n):
        # Extract the rolling window to find local min and max
        window = price[i - period + 1 : i + 1]
        max_h = np.max(window)
        min_l = np.min(window)

        # Normalize price to a range of -0.5 to +0.5, with recursive smoothing
        if max_h != min_l:
            value1 = 0.66 * ((price[i] - min_l) / (max_h - min_l) - 0.5) + 0.67 * value1

        # Constrain value to prevent math domain errors in the log function
        if value1 > 0.999:
            value1 = 0.999
        elif value1 < -0.999:
            value1 = -0.999

        # Apply the Fisher Transform: 0.5 * ln((1+X)/(1-X))
        fish = 0.5 * np.log((1.0 + value1) / (1.0 - value1)) + 0.5 * fish

        fisher[i] = fish
        trigger[i] = fish_prev  # The trigger line is simply the Fisher value delayed by 1 bar

        # Update previous state for the next recurrence
        fish_prev = fish

    return fisher, trigger
