import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates Fibonacci Retracement levels based on a lookback period.
    Levels: 0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0
    Supports standard OHLCV and MT4 (split date/time) formats with dynamic rounding.
    """

    # 1. Parse Parameters
    try:
        period = int(options.get('period', 100)) # Lookback for high/low
    except (ValueError, TypeError):
        period = 100

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
    is_mt4 = options.get('mt4') is True
    
    # 4. Dynamic Column Mapping
    if is_mt4:
        output_cols = ['date', 'time', 'fib_0', 'fib_382', 'fib_50', 'fib_618', 'fib_100']
        sort_cols = ['date', 'time']
    else:
        output_cols = ['symbol', 'timeframe', 'time', 'fib_0', 'fib_382', 'fib_50', 'fib_618', 'fib_100']
        sort_cols = ['time']

    # Convert numeric columns for calculation
    df['high'] = pd.to_numeric(df['high'], errors='coerce')
    df['low'] = pd.to_numeric(df['low'], errors='coerce')
    
    all_results = []
    group_keys = ['symbol', 'timeframe'] if not is_mt4 else None
    grouped = df.groupby(group_keys) if group_keys else [(None, df)]

    for _, group in grouped:
        group = group.sort_values(sort_cols).reset_index(drop=True)
        
        # 5. Find Rolling High and Low
        hh = group['high'].rolling(window=period).max()
        ll = group['low'].rolling(window=period).min()
        diff = (hh - ll).replace(0, 0.00000001)

        # 6. Calculate Levels
        group['fib_0'] = hh    # 0% level (Top)
        group['fib_236'] = hh - (0.236 * diff)
        group['fib_382'] = hh - (0.382 * diff)
        group['fib_50'] = hh - (0.5 * diff)
        group['fib_618'] = hh - (0.618 * diff)
        group['fib_786'] = hh - (0.786 * diff)
        group['fib_100'] = ll  # 100% level (Bottom)

        # 7. Apply Dynamic Rounding
        # Rounds all fib levels to match the asset's price precision
        fib_cols = ['fib_0', 'fib_236', 'fib_382', 'fib_50', 'fib_618', 'fib_786', 'fib_100']
        for col in fib_cols:
            if col in group.columns:
                group[col] = group[col].round(precision)

        # 8. Cleanup
        # Skip initial rows where the rolling window hasn't been satisfied
        group_clean = group.iloc[period:].copy()
        all_results.append(group_clean[output_cols])

    if not all_results:
        return [output_cols, []]

    # 9. Final Formatting
    final_df = pd.concat(all_results)
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by=sort_cols, ascending=is_asc)
    
    # Final safety gate for JSON compatibility (handles NaN/Inf)
    data_as_list = final_df.values.tolist()
    clean_data = [
        [(x if (isinstance(x, (float, np.floating)) and np.isfinite(x)) else x) for x in row]
        for row in data_as_list
    ]
    
    return [output_cols, clean_data]