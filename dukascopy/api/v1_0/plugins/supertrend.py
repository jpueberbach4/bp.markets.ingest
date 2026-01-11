import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates the Supertrend indicator.
    Fixed: Initialization seed, direction-based state tracking, and cleanup gaps.
    """

    # 1. Parse Parameters
    try:
        period = int(options.get('period', 10))
        multiplier = float(options.get('multiplier', 3.0))
    except (ValueError, TypeError):
        period, multiplier = 10, 3.0

    if not data:
        return [[], []]

    # 2. Prepare DataFrame
    df = pd.DataFrame(data)
    is_mt4 = options.get('mt4') is True
    
    if is_mt4:
        output_cols = ['date', 'time', 'supertrend', 'direction']
        sort_cols = ['date', 'time']
    else:
        output_cols = ['symbol', 'timeframe', 'time', 'supertrend', 'direction']
        sort_cols = ['time']

    # Ensure numeric conversion
    for col in ['high', 'low', 'close']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    all_results = []
    group_keys = ['symbol', 'timeframe'] if not is_mt4 else None
    grouped = df.groupby(group_keys) if group_keys else [(None, df)]

    for _, group in grouped:
        group = group.sort_values(sort_cols).reset_index(drop=True)
        
        # A. Calculate ATR (Wilder's Smoothing / EWM)
        prev_close = group['close'].shift(1)
        tr = pd.concat([
            group['high'] - group['low'],
            (group['high'] - prev_close).abs(),
            (group['low'] - prev_close).abs()
        ], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

        # B. Calculate Basic Upper and Lower Bands
        hl2 = (group['high'] + group['low']) / 2
        basic_ub = hl2 + (multiplier * atr)
        basic_lb = hl2 - (multiplier * atr)

        # C. Initialize arrays
        size = len(group)
        final_ub = np.zeros(size)
        final_lb = np.zeros(size)
        st = np.zeros(size)
        direction = np.zeros(size)

        # D. Recursive State Machine
        for i in range(size):
            if i < period:
                # Warmup: Populate basics so i-1 logic doesn't break
                final_ub[i] = basic_ub[i]
                final_lb[i] = basic_lb[i]
                st[i] = 0.0 # Will be cleaned later
                direction[i] = 1
                continue
            
            # Calculate Final Upper Band
            if basic_ub[i] < final_ub[i-1] or group['close'][i-1] > final_ub[i-1]:
                final_ub[i] = basic_ub[i]
            else:
                final_ub[i] = final_ub[i-1]

            # Calculate Final Lower Band
            if basic_lb[i] > final_lb[i-1] or group['close'][i-1] < final_lb[i-1]:
                final_lb[i] = basic_lb[i]
            else:
                final_lb[i] = final_lb[i-1]
            
            # Determine Trend Direction using explicit direction state
            if direction[i-1] == -1: # Previously Short
                if group['close'][i] > final_ub[i]:
                    direction[i] = 1
                    st[i] = final_lb[i]
                else:
                    direction[i] = -1
                    st[i] = final_ub[i]
            else: # Previously Long
                if group['close'][i] < final_lb[i]:
                    direction[i] = -1
                    st[i] = final_ub[i]
                else:
                    direction[i] = 1
                    st[i] = final_lb[i]

        group['supertrend'] = st
        group['direction'] = direction
        
        # E. Cleanup: Only drop the ATR warmup period
        # This prevents the middle-of-series gaps you were seeing
        group_clean = group.iloc[period:].copy()
        all_results.append(group_clean[output_cols])

    if not all_results:
        return [output_cols, []]

    final_df = pd.concat(all_results)
    
    # Sort results
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by=sort_cols, ascending=is_asc)
    
    # F. FINAL SAFETY GATE (JSON COMPLIANCE)
    data_as_list = final_df.values.tolist()
    clean_data = [
        [ (x if (isinstance(x, (float, np.floating)) and np.isfinite(x)) else x) for x in row ]
        for row in data_as_list
    ]
    
    # Ensure None is used for any remaining NaNs (for JSON null)
    clean_data = [[(None if (isinstance(val, float) and not np.isfinite(val)) else val) for val in row] for row in clean_data]
    
    return [output_cols, clean_data]