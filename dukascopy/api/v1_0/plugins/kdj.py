import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates KDJ Indicator (K, D, and J lines).
    Standard: 9-period lookback, 3-period slowing.
    J = 3D - 2K (Standard formula)
    """

    # 1. Parse Parameters
    try:
        n = int(options.get('n', 9))      # Lookback period
        m1 = int(options.get('m1', 3))    # K period
        m2 = int(options.get('m2', 3))    # D period
    except (ValueError, TypeError):
        n, m1, m2 = 9, 3, 3

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
    
    # 4. Dynamic Column Mapping
    if is_mt4:
        output_cols = ['date', 'time', 'k', 'd', 'j']
        sort_cols = ['date', 'time']
    else:
        output_cols = ['symbol', 'timeframe', 'time', 'k', 'd', 'j']
        sort_cols = ['time']

    # 5. Calculation Logic
    all_results = []
    group_keys = ['symbol', 'timeframe'] if not is_mt4 else None
    grouped = df.groupby(group_keys) if group_keys else [(None, df)]

    for _, group in grouped:
        group = group.sort_values(sort_cols).reset_index(drop=True)
        
        # RSV (Raw Stochastic Value)
        low_min = group['low'].rolling(window=n).min()
        high_max = group['high'].rolling(window=n).max()
        group['rsv'] = 100 * ((group['close'] - low_min) / (high_max - low_min))
        
        # Calculate K and D using Exponential Moving Average logic
        # Initialize K and D at 50 (standard practice)
        k_list, d_list = [], []
        k, d = 50.0, 50.0
        
        for rsv in group['rsv']:
            if np.isnan(rsv):
                k_list.append(np.nan)
                d_list.append(np.nan)
            else:
                k = ( (m1 - 1) * k + rsv ) / m1
                d = ( (m2 - 1) * d + k ) / m2
                k_list.append(k)
                d_list.append(d)
        
        group['k'], group['d'] = k_list, d_list
        
        # Calculate J line
        group['j'] = 3 * group['k'] - 2 * group['d']

        # 6. Apply Dynamic Rounding
        for col in ['k', 'd', 'j']:
            group[col] = group[col].round(precision)
        
        # 7. Filter and Collect
        all_results.append(group[output_cols].dropna(subset=['k']))

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