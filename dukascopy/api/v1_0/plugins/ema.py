import pandas as pd

def calculate(data, options):
    """
    Calculates Exponential Moving Average (EMA) per unique Symbol and Timeframe pair.
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
    # MT4 mode uses 'date' and 'time' separately instead of 'symbol', 'timeframe', 'time'
    if is_mt4:
        output_cols = ['date', 'time', 'ema']
        sort_cols = ['date', 'time']
    else:
        output_cols = ['symbol', 'timeframe', 'time', 'ema']
        sort_cols = ['time']

    # Ensure numeric types for calculation
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
        # Sort by the appropriate time columns for the format
        group = group.sort_values(sort_cols)
        
        # EMA Calculation using span
        group['ema'] = group['close'].ewm(span=period, adjust=False).mean()
        
        # Filter columns and drop the warm-up period
        all_results.append(group[output_cols].iloc[period:])

    if not all_results:
        return [output_cols, []]

    # 5. Final Formatting
    final_df = pd.concat(all_results)
    
    # Apply user-requested sort order
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by=sort_cols, ascending=is_asc)
    
    return [output_cols, final_df.values.tolist()]