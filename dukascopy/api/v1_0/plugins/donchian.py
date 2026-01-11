import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates Donchian Channels (Upper, Middle, Lower).
    Upper: Highest High over N periods.
    Lower: Lowest Low over N periods.
    Middle: (Upper + Lower) / 2.
    """

    # 1. Parse Parameters
    try:
        period = int(options.get('period', 20))
    except (ValueError, TypeError):
        period = 20

    if not data:
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
    
    # 4. Dynamic Column Mapping
    if is_mt4:
        output_cols = ['date', 'time', 'upper', 'mid', 'lower']
        sort_cols = ['date', 'time']
    else:
        output_cols = ['symbol', 'timeframe', 'time', 'upper', 'mid', 'lower']
        sort_cols = ['time']

    # Ensure numeric conversion
    for col in ['high', 'low']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    all_results = []
    group_keys = ['symbol', 'timeframe'] if not is_mt4 else None
    grouped = df.groupby(group_keys) if group_keys else [(None, df)]

    for _, group in grouped:
        group = group.sort_values(sort_cols).reset_index(drop=True)
        
        # 5. Calculation Logic
        group['upper'] = group['high'].rolling(window=period).max()
        group['lower'] = group['low'].rolling(window=period).min()
        group['mid'] = (group['upper'] + group['lower']) / 2

        # 6. Apply Dynamic Rounding
        for col in ['upper', 'mid', 'lower']:
            group[col] = group[col].round(precision)
        
        # 7. Cleanup and Append
        # Drop rows where the rolling window hasn't filled yet
        all_results.append(group[output_cols].dropna(subset=['upper']))

    if not all_results:
        return [output_cols, []]

    # 8. Final Formatting
    final_df = pd.concat(all_results)
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by=sort_cols, ascending=is_asc)
    
    # FINAL SAFETY GATE (JSON COMPLIANCE)
    data_as_list = final_df.values.tolist()
    clean_data = [
        [(x if (not isinstance(x, (float, np.floating)) or np.isfinite(x)) else None) for x in row]
        for row in data_as_list
    ]
    
    return [output_cols, clean_data]