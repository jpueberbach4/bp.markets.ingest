import pandas as pd
import numpy as np
from typing import List


def position_args(args: List):
    return {
        "period": args[0]
    }

def calculate(data, options):
    """
    Calculates Simple Moving Average (SMA) per unique Symbol and Timeframe pair.
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
    # Detects decimals from the first available close price to round the SMA output
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
        output_cols = ['date', 'time', 'sma']
        sort_cols = ['date', 'time']
    else:
        output_cols = ['symbol', 'timeframe', 'time', 'sma']
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
        
        # SMA Calculation: Rolling mean of closing prices
        group['sma'] = group['close'].rolling(window=period).mean()
        
        # 6. Apply Dynamic Rounding
        # Rounds the SMA values to match the asset's price precision
        group['sma'] = group['sma'].round(precision)
        
        # 7. Filter columns and remove the 'NaN' rows where the window hasn't filled yet
        all_results.append(group[output_cols].dropna(subset=['sma']))

    if not all_results:
        return [output_cols, []]

    # 8. Final Formatting
    final_df = pd.concat(all_results)
    
    # Apply user-requested sort order
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by=sort_cols, ascending=is_asc)
    
    # FINAL SAFETY GATE (JSON COMPLIANCE)
    # Replaces non-finite numbers like NaN or Inf with None (null)
    data_as_list = final_df.values.tolist()
    clean_data = [
        [(x if (isinstance(x, (float, np.floating)) and np.isfinite(x)) else x) for x in row]
        for row in data_as_list
    ]
    
    return [output_cols, clean_data]