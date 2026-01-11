import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates Williams %R.
    Formula: %R = (Highest High - Close) / (Highest High - Lowest Low) * -100
    Supports standard OHLCV and MT4 (split date/time) formats with dynamic rounding.
    """

    # 1. Parse Parameters
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14

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
        output_cols = ['date', 'time', 'williams_r']
        sort_cols = ['date', 'time']
    else:
        output_cols = ['symbol', 'timeframe', 'time', 'williams_r']
        sort_cols = ['time']

    # Ensure numeric conversion
    for col in ['high', 'low', 'close']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    all_results = []
    group_keys = ['symbol', 'timeframe'] if not is_mt4 else None
    grouped = df.groupby(group_keys) if group_keys else [(None, df)]

    for _, group in grouped:
        group = group.sort_values(sort_cols).reset_index(drop=True)
        
        # 5. Calculation Logic
        hh = group['high'].rolling(window=period).max()
        ll = group['low'].rolling(window=period).min()
        
        # Prevent division by zero if High == Low
        denom = (hh - ll).replace(0, np.nan)
        
        group['williams_r'] = ((hh - group['close']) / denom) * -100

        # 6. Apply Dynamic Rounding
        group['williams_r'] = group['williams_r'].round(precision)
        
        # 7. Cleanup and Append
        # Drop rows where the rolling window hasn't filled yet
        all_results.append(group[output_cols].dropna(subset=['williams_r']))

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