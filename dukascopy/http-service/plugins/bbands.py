import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates Bollinger Bands (Upper, Middle, Lower) per Symbol/Timeframe.
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

    # Prepare DataFrame
    df = pd.DataFrame(data)
    df['close'] = pd.to_numeric(df['close'])
    
    # We return the middle band (SMA), upper band, and lower band
    output_cols = ['symbol', 'timeframe', 'time', 'upper', 'mid', 'lower']
    all_results = []

    grouped = df.groupby(['symbol', 'timeframe'])

    for (symbol, timeframe), group in grouped:
        group = group.sort_values('time')
        
        # Middle Band (Simple Moving Average)
        group['mid'] = group['close'].rolling(window=period).mean()
        
        # Calculate Rolling Standard Deviation
        rolling_std = group['close'].rolling(window=period).std()
        
        # Upper and Lower Bands
        group['upper'] = group['mid'] + (rolling_std * std_dev)
        group['lower'] = group['mid'] - (rolling_std * std_dev)
        
        # Remove the 'NaN' rows from the start
        all_results.append(group[output_cols].dropna(subset=['mid']))

    if not all_results:
        return [output_cols, []]

    # 3. Final Formatting
    final_df = pd.concat(all_results)
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by='time', ascending=is_asc)
    
    return [output_cols, final_df.values.tolist()]