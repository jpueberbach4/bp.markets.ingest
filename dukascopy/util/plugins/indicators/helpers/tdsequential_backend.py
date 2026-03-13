import numpy as np

try:
    import numba
except ImportError:
    raise ImportError("Numba is required. Run 'pip install numba'")

@numba.jit(nopython=True, cache=True, nogil=True)
def _tdsequential_backend(close: np.ndarray, high: np.ndarray, low: np.ndarray):
    """
    Executes Tom DeMark's TD Sequential algorithm at C-speed.
    Produces sharp exhaustion spikes at +/- 9 and +/- 13, immediately resetting 
    to 0 afterward to provide the CNN with exact, pinpoint pivot targets.
    """
    n = len(close)
    setup = np.zeros(n)
    countdown = np.zeros(n)
    
    if n < 5: 
        return setup, countdown
        
    sell_setup_count = 0
    buy_setup_count = 0
    
    sell_countdown_count = 0
    buy_countdown_count = 0
    
    # 1 indicates active Sell countdown, -1 indicates active Buy countdown, 0 is inactive
    countdown_active = 0 

    for i in range(4, n):
        # ==========================================
        # PHASE 1: TD SETUP (Spikes at +/- 9)
        # ==========================================
        if close[i] > close[i-4]:
            sell_setup_count += 1
            buy_setup_count = 0
        elif close[i] < close[i-4]:
            buy_setup_count += 1
            sell_setup_count = 0
        else:
            # Equal closes break the strict sequence
            sell_setup_count = 0
            buy_setup_count = 0

        # Record the Setup state
        if sell_setup_count > 0:
            setup[i] = sell_setup_count
        elif buy_setup_count > 0:
            setup[i] = -buy_setup_count
        else:
            setup[i] = 0

        # EXACT PIVOT FIX: Trigger Countdown on exactly 9, then immediately reset Setup
        if sell_setup_count == 9:
            countdown_active = 1
            sell_countdown_count = 0
            sell_setup_count = 0  # Forces a sharp drop to 0 on the next bar
        elif buy_setup_count == 9:
            countdown_active = -1
            buy_countdown_count = 0
            buy_setup_count = 0   # Forces a sharp drop to 0 on the next bar

        # ==========================================
        # PHASE 2: TD COUNTDOWN (Spikes at +/- 13)
        # ==========================================
        if countdown_active == 1:
            # Sell Countdown: Close must be >= High 2 bars ago
            if i >= 2 and close[i] >= high[i-2]:
                sell_countdown_count += 1
                
            countdown[i] = sell_countdown_count
                
            # EXACT PIVOT FIX: Exhaustion reached, turn off and reset
            if sell_countdown_count == 13:
                countdown_active = 0 
                sell_countdown_count = 0  # Forces a sharp drop to 0 on the next bar
                
        elif countdown_active == -1:
            # Buy Countdown: Close must be <= Low 2 bars ago
            if i >= 2 and close[i] <= low[i-2]:
                buy_countdown_count += 1
                
            countdown[i] = -buy_countdown_count
                
            # EXACT PIVOT FIX: Exhaustion reached, turn off and reset
            if buy_countdown_count == 13:
                countdown_active = 0
                buy_countdown_count = 0   # Forces a sharp drop to 0 on the next bar
                
        else:
            countdown[i] = 0

    return setup, countdown