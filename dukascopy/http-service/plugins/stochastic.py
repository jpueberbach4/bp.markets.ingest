import pandas as pd

def calculate(data, options):
    """
    Calculates Stochastic Oscillator (%K and %D) per Symbol/Timeframe.
    Default: 14 period for %K, 3 period smoothing for %D.
    """

    # Parse Parameters
    try:
        k_period = int(options.get('k_period', 14))
        d_period = int(options.get('d_period', 3))
    except (ValueError, TypeError):
        k_period, d_period = 14, 3

    options['k_period'] = str(k_period)
    options['d_period'] = str(d_period)

    if not data:
        return [[], []]

    # Prepare DataFrame
    df = pd.DataFrame(data)
    df['close'] = pd.to_numeric(df['close'])
    df['high'] = pd.to_numeric(df['high'])
    df['low'] = pd.to_numeric(df['low'])
    
    output_cols = ['symbol', 'timeframe', 'time', 'stoch_k', 'stoch_d']
    all_results = []

    grouped = df.groupby(['symbol', 'timeframe'])

    for (symbol, timeframe), group in grouped:
        group = group.sort_values('time')
        
        # A. Calculate %K
        # %K = 100 * (Current Close - Lowest Low) / (Highest High - Lowest Low)
        low_min = group['low'].rolling(window=k_period).min()
        high_max = group['high'].rolling(window=k_period).max()
        
        group['stoch_k'] = 100 * (group['close'] - low_min) / (high_max - low_min)
        
        # B. Calculate %D (Simple Moving Average of %K)
        group['stoch_d'] = group['stoch_k'].rolling(window=d_period).mean()
        
        # Remove the 'NaN' rows from the start (k_period + d_period warmup)
        all_results.append(group[output_cols].dropna(subset=['stoch_d']))

    if not all_results:
        return [output_cols, []]

    # Final Formatting
    final_df = pd.concat(all_results)
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by='time', ascending=is_asc)
    
    return [output_cols, final_df.values.tolist()]