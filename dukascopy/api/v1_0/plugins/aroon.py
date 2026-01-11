import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates Aroon Indicator (Aroon Up and Aroon Down).
    Aroon Up = ((period - days since last period high) / period) * 100
    Aroon Down = ((period - days since last period low) / period) * 100
    """

    # 1. Parse Parameters
    try:
        period = int(options.get('period', 25))
    except (ValueError, TypeError):
        period = 25

    if not data:
        return [[], []]

    # 2. Determine Price Precision (Though Aroon is 0-100, we follow the pattern)
    try:
        sample_price = str(data[0].get('close', '0.00000'))
        precision = len(sample_price.split('.')[1]) if '.' in sample_price else 2
    except (IndexError, AttributeError):
        precision = 2

    # 3. Prepare DataFrame
    df = pd.DataFrame(data)
    is_mt4 = options.get('mt4') is True
    
    # 4. Dynamic Column Mapping
    if is_mt4:
        output_cols = ['date', 'time', 'aroon_up', 'aroon_down']
        sort_cols = ['date', 'time']
    else:
        output_cols = ['symbol', 'timeframe', 'time', 'aroon_up', 'aroon_down']
        sort_cols = ['time']

    # 5. Calculation Logic
    all_results = []
    group_keys = ['symbol', 'timeframe'] if not is_mt4 else None
    grouped = df.groupby(group_keys) if group_keys else [(None, df)]

    for _, group in grouped:
        group = group.sort_values(sort_cols).reset_index(drop=True)
        
        # Calculate periods since n-period high/low
        # We use apply with argmax to find the index of the extreme value in the window
        aroon_up = group['high'].rolling(window=period + 1).apply(
            lambda x: float(period - (period - x.argmax())), raw=False
        )
        
        aroon_down = group['low'].rolling(window=period + 1).apply(
            lambda x: float(period - (period - x.argmin())), raw=False
        )

        # Convert to percentage
        group['aroon_up'] = (aroon_up / period) * 100
        group['aroon_down'] = (aroon_down / period) * 100

        # 6. Apply Dynamic Rounding
        group['aroon_up'] = group['aroon_up'].round(precision)
        group['aroon_down'] = group['aroon_down'].round(precision)
        
        # 7. Filter and Collect
        all_results.append(group[output_cols].dropna(subset=['aroon_up']))

    if not all_results:
        return [output_cols, []]

    # 8. Final Formatting
    final_df = pd.concat(all_results)
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by=sort_cols, ascending=is_asc)
    
    # Final safety gate for JSON compatibility
    data_as_list = final_df.values.tolist()
    clean_data = [
        [(x if (not isinstance(x, (float, np.floating)) or np.isfinite(x)) else None) for x in row]
        for row in data_as_list
    ]
    
    return [output_cols, clean_data]