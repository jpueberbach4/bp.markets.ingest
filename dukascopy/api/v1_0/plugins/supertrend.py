import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates the Supertrend indicator.
    Formula: ATR-based trailing stop with trend direction logic.
    Supports standard OHLCV and MT4 (split date/time) formats with dynamic rounding.
    """

    # 1. Parse Parameters
    try:
        period = int(options.get('period', 10))
        multiplier = float(options.get('multiplier', 3.0))
    except (ValueError, TypeError):
        period, multiplier = 10, 3.0

    if not data:
        return [[], []]

    # 2. Determine Price Precision for Rounding
    try:
        sample_price = str(data[0].get('close', '0.00000'))
        precision = len(sample_price.split('.')[1]) if '.' in sample_price else 2
    except (IndexError, AttributeError):
        precision = 5

    # 3. Prepare DataFrame
    df = pd.DataFrame(data)
    is_mt4 = options.get('mt4') is True
    
    # 4. Dynamic Column Mapping
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
        group = group.sort_values(sort_cols)
        
        # 5. Calculate ATR (Wilder's Smoothing)
        prev_close = group['close'].shift(1)
        tr = pd.concat([
            group['high'] - group['low'],
            (group['high'] - prev_close).abs(),
            (group['low'] - prev_close).abs()
        ], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1/period, min_periods=period).mean()

        # 6. Basic Bands
        hl2 = (group['high'] + group['low']) / 2
        basic_ub = hl2 + (multiplier * atr)
        basic_lb = hl2 - (multiplier * atr)

        # 7. Final Upper and Lower Bands (Directional Logic)
        final_ub = np.zeros(len(group))
        final_lb = np.zeros(len(group))
        
        # FIX: Seed initial values to prevent 0.0/null on first reversal
        final_ub[0] = basic_ub.fillna(0).iloc[0]
        final_lb[0] = basic_lb.fillna(0).iloc[0]

        close_prices = group['close'].values
        bub = basic_ub.fillna(0).values
        blb = basic_lb.fillna(0).values

        for i in range(1, len(group)):
            # Final Upper Band logic
            if bub[i] < final_ub[i-1] or close_prices[i-1] > final_ub[i-1]:
                final_ub[i] = bub[i]
            else:
                final_ub[i] = final_ub[i-1]
                
            # Final Lower Band logic
            if blb[i] > final_lb[i-1] or close_prices[i-1] < final_lb[i-1]:
                final_lb[i] = blb[i]
            else:
                final_lb[i] = final_lb[i-1]

        # 8. Supertrend and Direction Tracking
        st = np.zeros(len(group))
        direction = np.ones(len(group)) # Default to 1 (Long)

        for i in range(1, len(group)):
            if direction[i-1] == -1: # Previously Short
                if close_prices[i] > final_ub[i]:
                    direction[i] = 1
                    st[i] = final_lb[i]
                else:
                    direction[i] = -1
                    st[i] = final_ub[i]
            else: # Previously Long
                if close_prices[i] < final_lb[i]:
                    direction[i] = -1
                    st[i] = final_ub[i]
                else:
                    direction[i] = 1
                    st[i] = final_lb[i]

        group['supertrend'] = st
        group['direction'] = direction
        
        # FIX: Replace any remaining 0.0 values with close price to ensure no nulls
        group.loc[group['supertrend'] == 0, 'supertrend'] = group['close']
        
        # 9. Apply Dynamic Rounding
        group['supertrend'] = group['supertrend'].round(precision)
        
        # 10. Cleanup: Skip ATR warmup period
        group_clean = group.iloc[period:].copy()
        all_results.append(group_clean[output_cols])

    if not all_results:
        return [output_cols, []]

    # 11. Final Formatting for JSON Compliance
    final_df = pd.concat(all_results)
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by=sort_cols, ascending=is_asc)
    
    # FINAL SAFETY GATE (JSON COMPLIANCE)
    # Replaces any stray NaN/Inf with None (null in JSON)
    data_as_list = final_df.values.tolist()
    clean_data = [
        [ (x if (not isinstance(x, (float, np.floating)) or np.isfinite(x)) else None) for x in row ]
        for row in data_as_list
    ]

    return [output_cols, clean_data]