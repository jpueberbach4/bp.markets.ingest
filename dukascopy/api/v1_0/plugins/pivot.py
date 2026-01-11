import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates Standard Pivot Points (Floor Pivots) with dynamic rounding.
    Matches the decimal precision of the input price data.
    """

    # 1. Parse Parameters
    try:
        period = int(options.get('period', 1))
    except (ValueError, TypeError):
        period = 1

    if not data:
        return [[], []]

    # 2. Determine Price Precision
    # Extract decimal places from the first available close price string
    try:
        sample_price = str(data[0].get('close', '0.00000'))
        precision = len(sample_price.split('.')[1]) if '.' in sample_price else 2
    except (IndexError, AttributeError):
        precision = 5

    # 3. Prepare DataFrame
    df = pd.DataFrame(data)
    is_mt4 = options.get('mt4') is True
    
    if is_mt4:
        output_cols = ['date', 'time', 'pp', 'r1', 's1', 'r2', 's2']
        sort_cols = ['date', 'time']
    else:
        output_cols = ['symbol', 'timeframe', 'time', 'pp', 'r1', 's1', 'r2', 's2']
        sort_cols = ['time']

    # Ensure numeric conversion
    for col in ['high', 'low', 'close']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    all_results = []
    group_keys = ['symbol', 'timeframe'] if not is_mt4 else None
    grouped = df.groupby(group_keys) if group_keys else [(None, df)]

    for _, group in grouped:
        group = group.sort_values(sort_cols).reset_index(drop=True)
        
        # 4. Get Previous Period High, Low, Close
        # We shift by 1 to use the completed previous period for current levels
        prev_h = group['high'].shift(1).rolling(window=period).max()
        prev_l = group['low'].shift(1).rolling(window=period).min()
        prev_c = group['close'].shift(1)

        # 5. Standard Pivot Calculations
        group['pp'] = (prev_h + prev_l + prev_c) / 3
        
        # Resistance Levels
        group['r1'] = (2 * group['pp']) - prev_l
        group['r2'] = group['pp'] + (prev_h - prev_l)
        
        # Support Levels
        group['s1'] = (2 * group['pp']) - prev_h
        group['s2'] = group['pp'] - (prev_h - prev_l)

        # 6. Apply Dynamic Rounding
        target_levels = ['pp', 'r1', 's1', 'r2', 's2']
        for level in target_levels:
            group[level] = group[level].round(precision)

        # 7. Cleanup and Collect
        # Skip the initial rows where lookback isn't satisfied
        group_clean = group.iloc[period + 1:].copy()
        all_results.append(group_clean[output_cols])

    if not all_results:
        return [output_cols, []]

    # 8. Final Formatting
    final_df = pd.concat(all_results)
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by=sort_cols, ascending=is_asc)
    
    # Final safety gate for JSON compatibility
    data_as_list = final_df.values.tolist()
    clean_data = [
        [ (x if (isinstance(x, (float, np.floating)) and np.isfinite(x)) else x) for x in row ]
        for row in data_as_list
    ]
    
    return [output_cols, clean_data]