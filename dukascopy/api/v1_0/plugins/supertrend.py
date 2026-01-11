import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates the Supertrend indicator.
    Fixed: Initialization seeds and zero-value fallbacks to prevent JSON nulls.
    """
    try:
        period = int(options.get('period', 10))
        multiplier = float(options.get('multiplier', 3.0))
    except (ValueError, TypeError):
        period, multiplier = 10, 3.0

    if not data: return [[], []]

    try:
        sample_price = str(data[0].get('close', '0.00000'))
        precision = len(sample_price.split('.')[1]) if '.' in sample_price else 2
    except (IndexError, AttributeError):
        precision = 5

    df = pd.DataFrame(data)
    is_mt4 = options.get('mt4') is True
    output_cols = ['date', 'time', 'supertrend', 'direction'] if is_mt4 else ['symbol', 'timeframe', 'time', 'supertrend', 'direction']
    sort_cols = ['date', 'time'] if is_mt4 else ['time']

    for col in ['high', 'low', 'close']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    all_results = []
    group_keys = ['symbol', 'timeframe'] if not is_mt4 else None
    grouped = df.groupby(group_keys) if group_keys else [(None, df)]

    for _, group in grouped:
        group = group.sort_values(sort_cols).reset_index(drop=True)
        
        # ATR Calculation
        prev_close = group['close'].shift(1)
        tr = pd.concat([
            group['high'] - group['low'],
            (group['high'] - prev_close).abs(),
            (group['low'] - prev_close).abs()
        ], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1/period, min_periods=period).mean()

        # Basic Bands
        hl2 = (group['high'] + group['low']) / 2
        basic_ub = hl2 + (multiplier * atr)
        basic_lb = hl2 - (multiplier * atr)

        # Final Bands - SEEDED to prevent 0.0 values
        final_ub = np.zeros(len(group))
        final_lb = np.zeros(len(group))
        
        # Initialize first index with basic bands to avoid 0.0 propagation
        final_ub[0] = basic_ub.fillna(group['high']).iloc[0]
        final_lb[0] = basic_lb.fillna(group['low']).iloc[0]

        for i in range(1, len(group)):
            # Upper Band logic: ensure we don't use 0.0 if basic_ub is NaN
            curr_bub = basic_ub[i] if not np.isnan(basic_ub[i]) else final_ub[i-1]
            if curr_bub < final_ub[i-1] or group['close'][i-1] > final_ub[i-1]:
                final_ub[i] = curr_bub
            else:
                final_ub[i] = final_ub[i-1]
                
            # Lower Band logic
            curr_blb = basic_lb[i] if not np.isnan(basic_lb[i]) else final_lb[i-1]
            if curr_blb > final_lb[i-1] or group['close'][i-1] < final_lb[i-1]:
                final_lb[i] = curr_blb
            else:
                final_lb[i] = final_lb[i-1]

        # Determine Supertrend
        st = np.zeros(len(group))
        direction = np.ones(len(group)) # Default to 1 (Long)

        for i in range(1, len(group)):
            if direction[i-1] == -1:
                if group['close'][i] > final_ub[i]:
                    direction[i], st[i] = 1, final_lb[i]
                else:
                    direction[i], st[i] = -1, final_ub[i]
            else:
                if group['close'][i] < final_lb[i]:
                    direction[i], st[i] = -1, final_ub[i]
                else:
                    direction[i], st[i] = 1, final_lb[i]

        group['supertrend'] = st
        group['direction'] = direction
        
        # FAILSAFE: If ST is 0.0 (happens during warmup/gaps), use close price
        # This prevents the Safety Gate from turning it into a null
        group.loc[group['supertrend'] == 0, 'supertrend'] = group['close']
        group['supertrend'] = group['supertrend'].round(precision)
        
        all_results.append(group.iloc[period:][output_cols])

    if not all_results: return [output_cols, []]
    final_df = pd.concat(all_results)
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by=sort_cols, ascending=is_asc)
    
    # SAFETY GATE
    data_as_list = final_df.values.tolist()
    clean_data = [[(x if (not isinstance(x, (float, np.floating)) or np.isfinite(x)) else None) for x in row] for row in data_as_list]

    return [output_cols, clean_data]