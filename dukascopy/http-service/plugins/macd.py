import pandas as pd

def calculate(data, options):
    """
    Calculates MACD per unique Symbol and Timeframe pair.
    Defaults: Fast=12, Slow=26, Signal=9
    """

    # Parse parameters from URI (e.g., /fast/12/slow/26/signal/9/)
    try:
        fast = int(options.get('fast', 12))
        slow = int(options.get('slow', 26))
        signal = int(options.get('signal', 9))
    except (ValueError, TypeError):
        fast, slow, signal = 12, 26, 9

    # Metadata for output
    options['fast'] = str(fast)
    options['slow'] = str(slow)
    options['signal'] = str(signal)

    if not data:
        return [[], []]

    df = pd.DataFrame(data)
    df['close'] = pd.to_numeric(df['close'])
    
    # We return all three components of the MACD
    output_cols = ['symbol', 'timeframe', 'time', 'macd', 'signal', 'hist']
    all_results = []

    grouped = df.groupby(['symbol', 'timeframe'])

    for (symbol, timeframe), group in grouped:
        group = group.sort_values('time')
        
        # Calculate Fast and Slow EMAs
        ema_fast = group['close'].ewm(span=fast, adjust=False).mean()
        ema_slow = group['close'].ewm(span=slow, adjust=False).mean()
        
        # MACD Line
        group['macd'] = ema_fast - ema_slow
        
        # Signal Line (EMA of the MACD Line)
        group['signal'] = group['macd'].ewm(span=signal, adjust=False).mean()
        
        # istogram
        group['hist'] = group['macd'] - group['signal']
        
        # Remove the warm-up period (usually the 'slow' period)
        all_results.append(group[output_cols].iloc[slow:])

    if not all_results:
        return [output_cols, []]

    final_df = pd.concat(all_results)
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by='time', ascending=is_asc)
    
    return [output_cols, final_df.values.tolist()]