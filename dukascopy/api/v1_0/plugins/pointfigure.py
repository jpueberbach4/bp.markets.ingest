import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates Point & Figure (P&F) chart data with multi-symbol grouping.
    X = Upward price movement (Demand)
    O = Downward price movement (Supply)
    """

    # 1. Parse Parameters
    try:
        box_size = float(options.get('box_size', 10.0))
        reversal = int(options.get('reversal', 3)) 
    except (ValueError, TypeError):
        box_size, reversal = 10.0, 3

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
        output_cols = ['date', 'time', 'column', 'type', 'price']
        sort_cols = ['date', 'time']
    else:
        output_cols = ['symbol', 'timeframe', 'time', 'column', 'type', 'price']
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
        
        symbol = keys[0] if not is_mt4 else None
        timeframe = keys[1] if not is_mt4 else None
        
        # P&F Logic Initialization
        current_col = 0
        last_h = np.floor(prices[0] / box_size) * box_size
        last_l = last_h
        is_up = True 
        
        group_results = []

        def add_pf_row(row_idx, col_val, type_val, price_val):
            res = []
            if not is_mt4:
                res.extend([symbol, timeframe, times[row_idx]])
            else:
                res.extend([group.loc[row_idx, 'date'], times[row_idx]])
            res.extend([col_val, type_val, round(price_val, precision)])
            group_results.append(res)

        for i in range(1, len(prices)):
            price = prices[i]

            if is_up:
                if price >= last_h + box_size:
                    num_boxes = int((price - last_h) // box_size)
                    for _ in range(num_boxes):
                        last_h += box_size
                        add_pf_row(i, current_col, 'X', last_h)
                elif price <= last_h - (box_size * reversal):
                    current_col += 1
                    num_boxes = int((last_h - price) // box_size)
                    last_l = last_h - box_size
                    for _ in range(num_boxes):
                        add_pf_row(i, current_col, 'O', last_l)
                        last_l -= box_size
                    last_l += box_size
                    is_up = False
            else:
                if price <= last_l - box_size:
                    num_boxes = int((last_l - price) // box_size)
                    for _ in range(num_boxes):
                        last_l -= box_size
                        add_pf_row(i, current_col, 'O', last_l)
                elif price >= last_l + (box_size * reversal):
                    current_col += 1
                    num_boxes = int((price - last_l) // box_size)
                    last_h = last_l + box_size
                    for _ in range(num_boxes):
                        add_pf_row(i, current_col, 'X', last_h)
                        last_h += box_size
                    last_h -= box_size
                    is_up = True

        all_results.extend(group_results)

    if not all_results:
        return [output_cols, []]

    # 5. Final Formatting and Sorting
    final_df = pd.DataFrame(all_results, columns=output_cols)
    is_asc = options.get('order', 'asc').lower() == 'asc'
    # Note: P&F is usually viewed linearly by column; 
    # we sort by temporal columns to maintain consistency with other plugins.
    final_df = final_df.sort_values(by=sort_cols, ascending=is_asc)
    
    # 6. JSON Safety Gate
    data_as_list = final_df.values.tolist()
    clean_data = [
        [(x if (isinstance(x, (float, np.floating)) and np.isfinite(x)) else x) for x in row]
        for row in data_as_list
    ]
    
    return [output_cols, clean_data]