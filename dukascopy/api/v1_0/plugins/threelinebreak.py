import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates Three Line Break (TLB) chart data.
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

    prices = [float(d['close']) for d in data]
    times = [d['time'] for d in data]
    
    output_cols = ['time', 'open', 'close', 'type']
    results = []

    # 3. Initialization
    # First line is based on the first two distinct prices
    first_price = prices[0]
    second_price = next((p for p in prices if p != first_price), first_price)
    
    lines = []
    lines.append({'open': first_price, 'close': second_price})
    results.append([times[0], round(first_price, precision), round(second_price, precision), 'initial'])

    # 4. TLB Logic
    for i in range(1, len(prices)):
        price = prices[i]
        time = times[i]
        
        last_line = lines[-1]
        is_up = last_line['close'] > last_line['open']
        
        # Scenario A: Trend Continuation
        if is_up and price > last_line['close']:
            new_line = {'open': last_line['close'], 'close': price}
            lines.append(new_line)
            results.append([time, round(new_line['open'], precision), round(new_line['close'], precision), 'up'])
        elif not is_up and price < last_line['close']:
            new_line = {'open': last_line['close'], 'close': price}
            lines.append(new_line)
            results.append([time, round(new_line['open'], precision), round(new_line['close'], precision), 'down'])
        
        # Scenario B: Reversal
        else:
            # Check the high/low of the last 'n' lines
            relevant_lines = lines[-break_count:]
            extreme_high = max([max(l['open'], l['close']) for l in relevant_lines])
            extreme_low = min([min(l['open'], l['close']) for l in relevant_lines])
            
            if is_up and price < extreme_low:
                new_line = {'open': last_line['close'], 'close': price}
                lines.append(new_line)
                results.append([time, round(new_line['open'], precision), round(new_line['close'], precision), 'reversal_down'])
            elif not is_up and price > extreme_high:
                new_line = {'open': last_line['close'], 'close': price}
                lines.append(new_line)
                results.append([time, round(new_line['open'], precision), round(new_line['close'], precision), 'reversal_up'])

    return [output_cols, results]