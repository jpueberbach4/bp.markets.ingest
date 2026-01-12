import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates Linear Regression Channel (Middle, Upper, Lower).
    Uses the Least Squares method to find the trend and sets 
    bands based on the price deviation.
    """

    # 1. Parse Parameters
    try:
        period = int(options.get('period', 50))
    except (ValueError, TypeError):
        period = 50

    if not data or len(data) < period:
        return [[], []]

    # 2. Determine Price Precision
    try:
        sample_price = str(data[0].get('close', '0.00000'))
        precision = len(sample_price.split('.')[1]) if '.' in sample_price else 2
    except (IndexError, AttributeError):
        precision = 5

    # 3. Prepare DataFrame
    df = pd.DataFrame(data)
    is_mt4 = options.get('mt4') is True
    
    if is_mt4:
        output_cols = ['date', 'time', 'lin_mid', 'lin_upper', 'lin_lower']
        sort_cols = ['date', 'time']
    else:
        output_cols = ['symbol', 'timeframe', 'time', 'lin_mid', 'lin_upper', 'lin_lower']
        sort_cols = ['time']

    df['close'] = pd.to_numeric(df['close'], errors='coerce')
    all_results = []
    group_keys = ['symbol', 'timeframe'] if not is_mt4 else None
    grouped = df.groupby(group_keys) if group_keys else [(None, df)]

    for _, group in grouped:
        group = group.sort_values(sort_cols).reset_index(drop=True)
        
        # 4. Linear Regression Logic
        # We use a rolling window to apply the linear regression formula
        # y = mx + b
        def get_lin_reg(series):
            y = series
            x = np.arange(len(y))
            # Perform linear regression
            slope, intercept = np.polyfit(x, y, 1)
            # The middle point of the channel is the end of the line
            mid_point = slope * (len(y) - 1) + intercept
            
            # Calculate deviation for the bands
            fitted_line = slope * x + intercept
            diff = np.abs(y - fitted_line)
            max_diff = np.max(diff) # Width of the channel
            
            return pd.Series([mid_point, mid_point + max_diff, mid_point - max_diff])

        res = group['close'].rolling(window=period).apply(
            lambda x: get_lin_reg(x).iloc[0], raw=True
        )
        
        # To avoid multiple rolling applies, we compute bands relative to mid
        group['lin_mid'] = group['close'].rolling(window=period).apply(
            lambda x: np.polyfit(np.arange(len(x)), x, 1)[0] * (len(x)-1) + np.polyfit(np.arange(len(x)), x, 1)[1], 
            raw=True
        )
        
        # Calculate the Deviation (width)
        def get_width(x):
            slope, intercept = np.polyfit(np.arange(len(x)), x, 1)
            line = slope * np.arange(len(x)) + intercept
            return np.max(np.abs(x - line))

        group['width'] = group['close'].rolling(window=period).apply(get_width, raw=True)
        
        group['lin_upper'] = group['lin_mid'] + group['width']
        group['lin_lower'] = group['lin_mid'] - group['width']

        # 5. Apply Dynamic Rounding
        for col in ['lin_mid', 'lin_upper', 'lin_lower']:
            group[col] = group[col].round(precision)
        
        all_results.append(group[output_cols].dropna(subset=['lin_mid']))

    if not all_results:
        return [output_cols, []]

    # 6. Final Formatting & JSON SAFETY GATE
    final_df = pd.concat(all_results)
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by=sort_cols, ascending=is_asc)
    
    data_as_list = final_df.values.tolist()
    clean_data = [
        [(x if (isinstance(x, (float, np.floating)) and np.isfinite(x)) else x) for x in row]
        for row in data_as_list
    ]
    
    return [output_cols, clean_data]