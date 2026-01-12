import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates Kagi Chart data with multi-symbol grouping and proper sorting.
    Yang = Thick line (Bullish, price > previous shoulder)
    Yin = Thin line (Bearish, price < previous waist)
    """

    # 1. Parse Parameters
    try:
        reversal = float(options.get('reversal', 10.0))
        is_percentage = options.get('mode', 'fixed') == 'percent'
    except (ValueError, TypeError):
        reversal, is_percentage = 10.0, False

    if not data:
        return [[], []]

    # 2. Determine Price Precision
    try:
        sample_price = str(data[0].get('close', '0.00000'))
        precision = len(sample_price.split('.')[1]) if '.' in sample_price else 2
    except (IndexError, AttributeError):
        precision = 2

    # 3. Prepare DataFrame
    df = pd.DataFrame(data)
    is_mt4 = options.get('mt4') is True
    
    if is_mt4:
        output_cols = ['date', 'time', 'price', 'direction', 'thickness', 'type']
        sort_cols = ['date', 'time']
    else:
        output_cols = ['symbol', 'timeframe', 'time', 'price', 'direction', 'thickness', 'type']
        sort_cols = ['time']

    df['close'] = pd.to_numeric(df['close'], errors='coerce')
    
    all_results = []
    group_keys = ['symbol', 'timeframe'] if not is_mt4 else None
    grouped = df.groupby(group_keys) if group_keys else [(None, df)]

    # 4. Process Each Group
    for keys, group in grouped:
        group = group.sort_values(sort_cols).reset_index(drop=True)
        prices = group['close'].values
        times = group['time'].values
        
        # Meta info for non-MT4 output
        symbol = keys[0] if not is_mt4 else None
        timeframe = keys[1] if not is_mt4 else None
        
        # Kagi Logic Initialization
        current_price = prices[0]
        direction = 0 # 1 for Up, -1 for Down
        thickness = 1 # 1 for Yang (Thick), 0 for Yin (Thin)
        prev_shoulder = float('-inf')
        prev_waist = float('inf')
        
        group_results = []
        
        def add_kagi_row(time_val, price_val, dir_val, thick_val, type_val, row_idx):
            res = []
            if not is_mt4:
                res.extend([symbol, timeframe])
            else:
                # Add date for MT4 from the original dataframe row
                res.append(group.loc[row_idx, 'date'])
            res.extend([time_val, round(price_val, precision), dir_val, thick_val, type_val])
            group_results.append(res)

        add_kagi_row(times[0], current_price, 0, thickness, 'start', 0)

        for i in range(1, len(prices)):
            price = prices[i]
            time = times[i]
            rev_amt = (current_price * (reversal / 100)) if is_percentage else reversal

            if direction == 0:
                if price >= current_price + rev_amt:
                    direction = 1
                    current_price = price
                elif price <= current_price - rev_amt:
                    direction = -1
                    current_price = price
            
            elif direction == 1: # Moving Up
                if price >= current_price:
                    current_price = price
                    if current_price > prev_shoulder: thickness = 1
                elif price <= current_price - rev_amt:
                    prev_shoulder = current_price
                    direction = -1
                    current_price = price
                    add_kagi_row(time, prev_shoulder, -1, thickness, 'shoulder', i)
                    if current_price < prev_waist: thickness = 0

            elif direction == -1: # Moving Down
                if price <= current_price:
                    current_price = price
                    if current_price < prev_waist: thickness = 0
                elif price >= current_price + rev_amt:
                    prev_waist = current_price
                    direction = 1
                    current_price = price
                    add_kagi_row(time, prev_waist, 1, thickness, 'waist', i)
                    if current_price > prev_shoulder: thickness = 1

        all_results.extend(group_results)

    if not all_results:
        return [output_cols, []]

    # 5. Final Formatting and Sorting
    final_df = pd.DataFrame(all_results, columns=output_cols)
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by=sort_cols, ascending=is_asc)
    
    # 6. JSON Safety Gate (Handles NaN/Inf)
    data_as_list = final_df.values.tolist()
    clean_data = [
        [(x if (isinstance(x, (float, np.floating)) and np.isfinite(x)) else x) for x in row]
        for row in data_as_list
    ]
    
    return [output_cols, clean_data]