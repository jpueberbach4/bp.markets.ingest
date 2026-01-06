import pandas as pd

def calculate(data, options):
    """
    Calculates Simple Moving Average (SMA) per unique Symbol and Timeframe pair.
    """

    # 1. Parse and validate period
    raw_period = options.get('period', 14)
    try:
        period = int(raw_period)
    except (ValueError, TypeError):
        period = 14

    # Update options so it's visible in the output metadata
    options['period'] = str(period)

    if not data:
        return [[], []]

    # Prepare DataFrame
    df = pd.DataFrame(data)
    df['close'] = pd.to_numeric(df['close'])
    
    output_cols = ['symbol', 'timeframe', 'time', 'sma']
    all_results = []

    # Group and Calculate
    grouped = df.groupby(['symbol', 'timeframe'])

    for (symbol, timeframe), group in grouped:
        # Sort by time to ensure the SMA is calculated chronologically
        group = group.sort_values('time')
        
        # SMA Calculation: sum of last N closes / N
        group['sma'] = group['close'].rolling(window=period).mean()
        
        # Remove the 'NaN' rows where the window hasn't filled yet
        all_results.append(group[output_cols].dropna(subset=['sma']))

    if not all_results:
        return [output_cols, []]

    # Final Formatting
    final_df = pd.concat(all_results)
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by='time', ascending=is_asc)
    
    return [output_cols, final_df.values.tolist()]