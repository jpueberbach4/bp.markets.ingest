import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates Bollinger Bands (Upper, Middle, Lower) per Symbol/Timeframe.
    Supports standard OHLCV and MT4 (split date/time) formats.
    Default: 20 period, 2 Standard Deviations.
    """

    # 1. Parse Parameters
    try:
        period = int(options.get('period', 20))
        std_dev = float(options.get('std', 2.0))
    except (ValueError, TypeError):
        period, std_dev = 20, 2.0

    options['period'] = str(period)
    options['std'] = str(std_dev)

    if not data:
        return [[], []]

    # 2. Prepare DataFrame
    df = pd.DataFrame(data)
    
    # Detect MT4 mode
    is_mt4 = options.get('mt4') is True
    
    # 3. Dynamic Column Mapping
    # MT4 mode uses 'date' and 'time' separately
    if is_mt4:
        output_cols = ['date', 'time', 'upper', 'mid', 'lower']
        sort_cols = ['date', 'time']
    else:
        output_cols = ['symbol', 'timeframe', 'time', 'upper', 'mid', 'lower']
        sort_cols = ['time']

    # Ensure numeric type for calculations
    df['close'] = pd.to_numeric(df['close'], errors='coerce')
    
    all_results = []

    # 4. Group and Calculate
    # MT4 queries are restricted to a single selection in routes.py
    group_keys = ['symbol', 'timeframe'] if not is_mt4 else None

    if group_keys:
        grouped = df.groupby(group_keys)
    else:
        grouped = [(None, df)]

    for _, group in grouped:
        # Sort using the correct temporal columns
        group = group.sort_values(sort_cols)
        
        # Middle Band (Simple Moving Average)
        group['mid'] = group['close'].rolling(window=period).mean()
        
        # Calculate Rolling Standard Deviation
        rolling_std = group['close'].rolling(window=period).std()
        
        # Upper and Lower Bands
        group['upper'] = group['mid'] + (rolling_std * std_dev)
        group['lower'] = group['mid'] - (rolling_std * std_dev)
        
        # Remove the 'NaN' rows from the warm-up period
        all_results.append(group[output_cols].dropna(subset=['mid']))

    if not all_results:
        return [output_cols, []]

    # 5. Final Formatting
    final_df = pd.concat(all_results)
    
    # Apply user-requested sort order
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by=sort_cols, ascending=is_asc)
    
    return [output_cols, final_df.values.tolist()]