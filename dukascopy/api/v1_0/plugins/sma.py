import pandas as pd

def calculate(data, options):
    """
    Calculates Simple Moving Average (SMA) per unique Symbol and Timeframe pair.
    Supports standard OHLCV and MT4 (split date/time) formats.
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

    # 2. Prepare DataFrame
    df = pd.DataFrame(data)
    
    # Detect MT4 mode
    is_mt4 = options.get('mt4') is True
    
    # 3. Dynamic Column Mapping
    # MT4 mode uses 'date' and 'time' separately (see helper.py generate_sql)
    if is_mt4:
        output_cols = ['date', 'time', 'sma']
        sort_cols = ['date', 'time']
    else:
        output_cols = ['symbol', 'timeframe', 'time', 'sma']
        sort_cols = ['time']

    # Ensure numeric type for calculations
    df['close'] = pd.to_numeric(df['close'], errors='coerce')
    
    all_results = []

    # 4. Group and Calculate
    # MT4 queries are restricted to a single symbol/timeframe in routes.py
    group_keys = ['symbol', 'timeframe'] if not is_mt4 else None

    if group_keys:
        grouped = df.groupby(group_keys)
    else:
        grouped = [(None, df)]

    for _, group in grouped:
        # Sort using the correct temporal columns (date/time for MT4 or time for standard)
        group = group.sort_values(sort_cols)
        
        # SMA Calculation: Rolling mean of closing prices
        group['sma'] = group['close'].rolling(window=period).mean()
        
        # Filter columns and remove the 'NaN' rows where the window hasn't filled yet
        all_results.append(group[output_cols].dropna(subset=['sma']))

    if not all_results:
        return [output_cols, []]

    # 5. Final Formatting
    final_df = pd.concat(all_results)
    
    # Apply user-requested sort order
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by=sort_cols, ascending=is_asc)
    
    return [output_cols, final_df.values.tolist()]