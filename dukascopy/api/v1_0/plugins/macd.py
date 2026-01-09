import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates MACD per unique Symbol and Timeframe pair.
    Supports standard OHLCV and MT4 (split date/time) formats.
    Defaults: Fast=12, Slow=26, Signal=9
    """

    # 1. Parse parameters
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

    # 2. Prepare DataFrame
    df = pd.DataFrame(data)
    
    # Detect MT4 mode
    is_mt4 = options.get('mt4') is True
    
    # 3. Dynamic Column Mapping
    # MT4 mode uses 'date' and 'time' separately (see helper.py generate_sql)
    if is_mt4:
        output_cols = ['date', 'time', 'macd', 'signal', 'hist']
        sort_cols = ['date', 'time']
    else:
        output_cols = ['symbol', 'timeframe', 'time', 'macd', 'signal', 'hist']
        sort_cols = ['time']

    # Ensure numeric types for calculation
    df['close'] = pd.to_numeric(df['close'], errors='coerce')
    
    all_results = []

    # 4. Group and Calculate
    # MT4 flag requires single-symbol selects in routes.py
    group_keys = ['symbol', 'timeframe'] if not is_mt4 else None

    if group_keys:
        grouped = df.groupby(group_keys)
    else:
        grouped = [(None, df)]

    for _, group in grouped:
        # Sort by the appropriate time columns
        group = group.sort_values(sort_cols)
        
        # Calculate Fast and Slow EMAs
        ema_fast = group['close'].ewm(span=fast, adjust=False).mean()
        ema_slow = group['close'].ewm(span=slow, adjust=False).mean()
        
        # MACD Line
        group['macd'] = ema_fast - ema_slow
        
        # Signal Line (EMA of the MACD Line)
        group['signal'] = group['macd'].ewm(span=signal, adjust=False).mean()
        
        # Histogram
        group['hist'] = group['macd'] - group['signal']
        
        # Filter columns and remove the warm-up period (usually based on 'slow')
        all_results.append(group[output_cols].iloc[slow:])

    if not all_results:
        return [output_cols, []]

    # 5. Final Formatting
    final_df = pd.concat(all_results)
    
    # Apply user-requested sort order
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by=sort_cols, ascending=is_asc)
    
    return [output_cols, final_df.values.tolist()]