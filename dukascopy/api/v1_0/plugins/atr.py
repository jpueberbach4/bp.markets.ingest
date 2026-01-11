import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates Average True Range (ATR) per Symbol/Timeframe.
    Supports standard OHLCV and MT4 (split date/time) formats with dynamic rounding.
    """

    # 1. Parse Period with fallback to 14
    raw_period = options.get('period', 14)
    try:
        period = int(raw_period)
    except (ValueError, TypeError):
        period = 14

    options['period'] = str(period)

    if not data:
        return [[], []]

    # 2. Determine Price Precision
    # Detects decimals from the first available close price to round output
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
        output_cols = ['date', 'time', 'atr']
        sort_cols = ['date', 'time']
    else:
        output_cols = ['symbol', 'timeframe', 'time', 'atr']
        sort_cols = ['time']

    # Ensure numeric types for calculation
    for col in ['close', 'high', 'low']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    all_results = []

    # 5. Group and Calculate
    group_keys = ['symbol', 'timeframe'] if not is_mt4 else None
    grouped = df.groupby(group_keys) if group_keys else [(None, df)]

    for _, group in grouped:
        # Sort by the appropriate time columns
        group = group.sort_values(sort_cols).reset_index(drop=True)
        
        # A. Calculate True Range (TR)
        prev_close = group['close'].shift(1)
        
        tr1 = group['high'] - group['low']
        tr2 = (group['high'] - prev_close).abs()
        tr3 = (group['low'] - prev_close).abs()
        
        group['tr'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # B. Calculate ATR using Wilder's Smoothing
        # alpha = 1/period is equivalent to ewm(com=period-1)
        group['atr'] = group['tr'].ewm(com=period - 1, min_periods=period).mean()
        
        # C. Apply Dynamic Rounding
        # Rounds ATR to match price precision
        group['atr'] = group['atr'].round(precision)
        
        # D. Filter and Collect
        all_results.append(group[output_cols].dropna(subset=['atr']))

    if not all_results:
        return [output_cols, []]

    # 6. Final Formatting
    final_df = pd.concat(all_results)
    
    # Apply user-requested ordering
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by=sort_cols, ascending=is_asc)
    
    # Final safety gate for JSON compatibility (handles NaN/Inf)
    data_as_list = final_df.values.tolist()
    clean_data = [
        [(x if (isinstance(x, (float, np.floating)) and np.isfinite(x)) else x) for x in row]
        for row in data_as_list
    ]
    
    return [output_cols, clean_data]