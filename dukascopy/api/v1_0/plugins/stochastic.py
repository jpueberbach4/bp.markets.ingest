import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates Stochastic Oscillator (%K and %D) per Symbol/Timeframe.
    Supports standard OHLCV and MT4 (split date/time) formats with dynamic rounding.
    Default: 14 period for %K, 3 period smoothing for %D.
    """

    # 1. Parse Parameters
    try:
        k_period = int(options.get('k_period', 14))
        d_period = int(options.get('d_period', 3))
    except (ValueError, TypeError):
        k_period, d_period = 14, 3

    options['k_period'] = str(k_period)
    options['d_period'] = str(d_period)

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
        output_cols = ['date', 'time', 'stoch_k', 'stoch_d']
        sort_cols = ['date', 'time']
    else:
        output_cols = ['symbol', 'timeframe', 'time', 'stoch_k', 'stoch_d']
        sort_cols = ['time']

    # Ensure numeric type for calculations
    for col in ['high', 'low', 'close']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    all_results = []

    # 5. Group and Calculate
    group_keys = ['symbol', 'timeframe'] if not is_mt4 else None
    grouped = df.groupby(group_keys) if group_keys else [(None, df)]

    for _, group in grouped:
        # Sort by the appropriate temporal columns
        group = group.sort_values(sort_cols).reset_index(drop=True)
        
        # A. Calculate %K
        # %K = 100 * (Current Close - Lowest Low) / (Highest High - Lowest Low)
        low_min = group['low'].rolling(window=k_period).min()
        high_max = group['high'].rolling(window=k_period).max()
        
        # Handle division by zero if high and low are the same
        denom = high_max - low_min
        group['stoch_k'] = 100 * (group['close'] - low_min) / denom.replace(0, np.nan)
        
        # B. Calculate %D (Simple Moving Average of %K)
        group['stoch_d'] = group['stoch_k'].rolling(window=d_period).mean()
        
        # 6. Apply Dynamic Rounding
        # Rounds both Stochastic lines to match the asset's price precision
        for col in ['stoch_k', 'stoch_d']:
            group[col] = group[col].round(precision)
        
        # 7. Filter and Collect
        # Remove the 'NaN' rows from the start
        all_results.append(group[output_cols].dropna(subset=['stoch_d']))

    if not all_results:
        return [output_cols, []]

    # 8. Final Formatting
    final_df = pd.concat(all_results)
    
    # Apply user-requested sort order
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by=sort_cols, ascending=is_asc)
    
    # FINAL SAFETY GATE (JSON COMPLIANCE)
    # Replaces non-finite numbers like NaN or Inf with None (null)
    data_as_list = final_df.values.tolist()
    clean_data = [
        [(x if (isinstance(x, (float, np.floating)) and np.isfinite(x)) else x) for x in row]
        for row in data_as_list
    ]
    
    return [output_cols, clean_data]