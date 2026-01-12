import pandas as pd
import numpy as np
from typing import List

def position_args(args: List):
    return {
        "fast": args[0],
        "slow": args[1],
        "signal": args[2]
    }

def calculate(data, options):
    """
    Calculates MACD per unique Symbol and Timeframe pair.
    Supports standard OHLCV and MT4 (split date/time) formats with dynamic rounding.
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

    # 2. Determine Price Precision
    # Detects decimals from the first available close price to round output levels
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
        output_cols = ['date', 'time', 'macd', 'signal', 'hist']
        sort_cols = ['date', 'time']
    else:
        output_cols = ['symbol', 'timeframe', 'time', 'macd', 'signal', 'hist']
        sort_cols = ['time']

    # Ensure numeric types for calculation
    df['close'] = pd.to_numeric(df['close'], errors='coerce')
    
    all_results = []

    # 5. Group and Calculate
    group_keys = ['symbol', 'timeframe'] if not is_mt4 else None
    grouped = df.groupby(group_keys) if group_keys else [(None, df)]

    for _, group in grouped:
        # Sort by the appropriate time columns
        group = group.sort_values(sort_cols).reset_index(drop=True)
        
        # A. Calculate Fast and Slow EMAs
        ema_fast = group['close'].ewm(span=fast, adjust=False).mean()
        ema_slow = group['close'].ewm(span=slow, adjust=False).mean()
        
        # B. MACD Line
        group['macd'] = ema_fast - ema_slow
        
        # C. Signal Line (EMA of the MACD Line)
        group['signal'] = group['macd'].ewm(span=signal, adjust=False).mean()
        
        # D. Histogram
        group['hist'] = group['macd'] - group['signal']
        
        # 6. Apply Dynamic Rounding
        # Rounds MACD, Signal, and Histogram to match price precision
        for col in ['macd', 'signal', 'hist']:
            group[col] = group[col].round(precision)
        
        # 7. Filter and Collect
        # Remove the warm-up period (usually based on 'slow')
        all_results.append(group[output_cols].iloc[slow:])

    if not all_results:
        return [output_cols, []]

    # 8. Final Formatting
    final_df = pd.concat(all_results)
    
    # Apply user-requested sort order
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by=sort_cols, ascending=is_asc)
    
    # FINAL SAFETY GATE (JSON COMPLIANCE)
    # Handles non-finite numbers like NaN or Inf
    data_as_list = final_df.values.tolist()
    clean_data = [
        [(x if (isinstance(x, (float, np.floating)) and np.isfinite(x)) else x) for x in row]
        for row in data_as_list
    ]
    
    return [output_cols, clean_data]