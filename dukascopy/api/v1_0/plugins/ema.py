import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates Exponential Moving Average (EMA) per unique Symbol and Timeframe pair.
    Supports standard OHLCV and MT4 (split date/time) formats with dynamic rounding.
    """

    # 1. Parse and validate period
    raw_period = options.get('period', 14)
    try:
        period = int(raw_period)
    except (ValueError, TypeError):
        period = 14

    options['period'] = str(period)

    if not data:
        return [[], []]

    # 2. Determine Price Precision
    # Detects decimals from the first available close price to round the EMA output
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
        output_cols = ['date', 'time', 'ema']
        sort_cols = ['date', 'time']
    else:
        output_cols = ['symbol', 'timeframe', 'time', 'ema']
        sort_cols = ['time']

    # Ensure numeric types for calculation
    df['close'] = pd.to_numeric(df['close'], errors='coerce')
    
    all_results = []

    # 5. Group and Calculate
    group_keys = ['symbol', 'timeframe'] if not is_mt4 else None
    grouped = df.groupby(group_keys) if group_keys else [(None, df)]

    for _, group in grouped:
        # Sort by the appropriate time columns for the format
        group = group.sort_values(sort_cols).reset_index(drop=True)
        
        # EMA Calculation using span
        group['ema'] = group['close'].ewm(span=period, adjust=False).mean()
        
        # 6. Apply Dynamic Rounding
        # Rounds the EMA values to match the asset's price precision
        group['ema'] = group['ema'].round(precision)
        
        # 7. Filter columns and drop the warm-up period
        all_results.append(group[output_cols].iloc[period:])

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