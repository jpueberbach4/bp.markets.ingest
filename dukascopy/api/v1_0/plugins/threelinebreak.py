import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates Three Line Break (TLB) chart data with multi-symbol grouping.
    A reversal occurs only if the current price breaks the high/low 
    of the previous 'n' lines (default is 3).
    """

    # 1. Parse Parameters
    try:
        break_count = int(options.get('break', 3))
    except (ValueError, TypeError):
        break_count = 3

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
        output_cols = ['date', 'time', 'open', 'close', 'type']
        sort_cols = ['date', 'time']
    else:
        output_cols = ['symbol', 'timeframe', 'time', 'open', 'close', 'type']
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
        
        # TLB Logic Initialization
        first_price = prices[0]
        second_price = next((p for p in prices if p != first_price), first_price)
        
        lines = []
        lines.append({'open': first_price, 'close': second_price})
        
        group_results = []

        def add_tlb_row(row_idx, open_val, close_val, type_str):
            res = []
            if not is_mt4:
                res.extend([symbol, timeframe, times[row_idx]])
            else:
                res.extend([group.loc[row_idx, 'date'], times[row_idx]])
            res.extend([round(open_val, precision), round(close_val, precision), type_str])
            group_results.append(res)

        add_tlb_row(0, first_price, second_price, 'initial')

        for i in range(1, len(prices)):
            price = prices[i]
            last_line = lines[-1]
            is_up = last_line['close'] > last_line['open']
            
            # Scenario A: Trend Continuation
            if is_up and price > last_line['close']:
                new_line = {'open': last_line['close'], 'close': price}
                lines.append(new_line)
                add_tlb_row(i, new_line['open'], new_line['close'], 'up')
            elif not is_up and price < last_line['close']:
                new_line = {'open': last_line['close'], 'close': price}
                lines.append(new_line)
                add_tlb_row(i, new_line['open'], new_line['close'], 'down')
            
            # Scenario B: Reversal Check
            else:
                relevant_lines = lines[-break_count:]
                extreme_high = max([max(l['open'], l['close']) for l in relevant_lines])
                extreme_low = min([min(l['open'], l['close']) for l in relevant_lines])
                
                if is_up and price < extreme_low:
                    new_line = {'open': last_line['close'], 'close': price}
                    lines.append(new_line)
                    add_tlb_row(i, new_line['open'], new_line['close'], 'reversal_down')
                elif not is_up and price > extreme_high:
                    new_line = {'open': last_line['close'], 'close': price}
                    lines.append(new_line)
                    add_tlb_row(i, new_line['open'], new_line['close'], 'reversal_up')

        all_results.extend(group_results)

    if not all_results:
        return [output_cols, []]

    # 5. Final Formatting and Sorting
    final_df = pd.DataFrame(all_results, columns=output_cols)
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by=sort_cols, ascending=is_asc)
    
    # 6. JSON Safety Gate
    data_as_list = final_df.values.tolist()
    clean_data = [
        [(x if (isinstance(x, (float, np.floating)) and np.isfinite(x)) else x) for x in row]
        for row in data_as_list
    ]
    
    return [output_cols, clean_data]