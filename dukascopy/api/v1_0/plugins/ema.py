import pandas as pd

def calculate(data, options):
    """
    Calculates Exponential Moving Average (EMA) per unique Symbol and Timeframe pair.
    """

    # Parse and validate period
    raw_period = options.get('period', 14)
    try:
        period = int(raw_period)
    except (ValueError, TypeError):
        period = 14

    options['period'] = str(period)

    if not data:
        return [[], []]

    # Prepare DataFrame
    df = pd.DataFrame(data)
    df['close'] = pd.to_numeric(df['close'])
    
    output_cols = ['symbol', 'timeframe', 'time', 'ema']
    all_results = []

    # Group and Calculate
    grouped = df.groupby(['symbol', 'timeframe'])

    for (symbol, timeframe), group in grouped:
        group = group.sort_values('time')
        
        # EMA Calculation using span
        # span=period is the standard way to define EMA period in pandas
        group['ema'] = group['close'].ewm(span=period, adjust=False).mean()
        
        # Unlike SMA, EMA technically starts from the first row, 
        # but we drop the first 'period' rows to ensure stability
        all_results.append(group[output_cols].iloc[period:])

    if not all_results:
        return [output_cols, []]

    # Final Formatting
    final_df = pd.concat(all_results)
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by='time', ascending=is_asc)
    
    return [output_cols, final_df.values.tolist()]