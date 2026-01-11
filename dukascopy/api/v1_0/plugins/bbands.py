import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates Bollinger Bands (Upper, Middle, Lower) per Symbol/Timeframe.
    Supports standard OHLCV and MT4 (split date/time) formats with dynamic rounding.
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

    # 2. Determine Price Precision
    # Detects decimals from the first available close price to round output levels
    try:
        sample_price = str(data[0].get('close', '0.00000'))
        precision = len(sample_price.split('.')[1]) if '.' in sample_price else 2
    except (IndexError, AttributeError):
        precision = 5

    # 3. Prepare DataFrame
    df = pd.DataFrame(data)
    
    # Detect MT4 mode
    is_mt4 = options.get('mt4') is True
    
    # 4. Dynamic Column Mapping
    if is_mt4:
        output_cols = ['date', 'time', 'upper', 'mid', 'lower']
        sort_cols = ['date', 'time']
    else:
        output_cols = ['symbol', 'timeframe', 'time', 'upper', 'mid', 'lower']
        sort_cols = ['time']

    # Ensure numeric type for calculations
    df['close'] = pd.to_numeric(df['close'], errors='coerce')
    
    all_results = []

    # 5. Group and Calculate
    group_keys = ['symbol', 'timeframe'] if not is_mt4 else None
    grouped = df.groupby(group_keys) if group_keys else [(None, df)]

    for _, group in grouped:
        # Sort using the correct temporal columns
        group = group.sort_values(sort_cols).reset_index(drop=True)
        
        # Middle Band (Simple Moving Average)
        group['mid'] = group['close'].rolling(window=period).mean()
        
        # Calculate Rolling Standard Deviation
        rolling_std = group['close'].rolling(window=period).std()
        
        # Upper and Lower Bands
        group['upper'] = group['mid'] + (rolling_std * std_dev)
        group['lower'] = group['mid'] - (rolling_std * std_dev)
        
        # 6. Apply Dynamic Rounding
        # Rounds all band levels to match the asset's price precision
        for col in ['upper', 'mid', 'lower']:
            group[col] = group[col].round(precision)
        
        # 7. Filter and Collect
        all_results.append(group[output_cols].dropna(subset=['mid']))

    if not all_results:
        return [output_cols, []]

    # 8. Final Formatting
    final_df = pd.concat(all_results)
    
    # Apply user-requested sort order
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by=sort_cols, ascending=is_asc)
    
    # Final safety gate for JSON compatibility (handles NaN/Inf)
    data_as_list = final_df.values.tolist()
    clean_data = [
        [(x if (isinstance(x, (float, np.floating)) and np.isfinite(x)) else x) for x in row]
        for row in data_as_list
    ]
    
    return [output_cols, clean_data]