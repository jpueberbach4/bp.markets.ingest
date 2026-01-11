import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates RSI per unique Symbol and Timeframe pair.
    Supports standard OHLCV and MT4 (split date/time) formats with dynamic rounding.
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

    # 2. Determine Price Precision
    # Detects decimals from the first available close price to round the RSI output
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
        output_cols = ['date', 'time', 'rsi']
        sort_cols = ['date', 'time']
    else:
        output_cols = ['symbol', 'timeframe', 'time', 'rsi']
        sort_cols = ['time']

    # Ensure numeric types for calculation
    df['close'] = pd.to_numeric(df['close'], errors='coerce')
    
    all_results = []

    # 5. Group and Calculate
    group_keys = ['symbol', 'timeframe'] if not is_mt4 else None
    grouped = df.groupby(group_keys) if group_keys else [(None, df)]

    for _, group in grouped:
        # Sort by the appropriate time columns to ensure chronological RSI calculation
        group = group.sort_values(sort_cols).reset_index(drop=True)
        
        # RSI Calculation Logic
        delta = group['close'].diff()
        gain = (delta.where(delta > 0, 0))
        loss = (-delta.where(delta < 0, 0))

        # Wilder's Smoothing / EMA (alpha = 1/period)
        avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
        avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()

        rs = avg_gain / avg_loss
        group['rsi'] = 100 - (100 / (1 + rs))
        
        # 6. Apply Dynamic Rounding
        # Rounds the RSI values to match the asset's price precision
        group['rsi'] = group['rsi'].round(precision)
        
        # 7. Filter columns and remove the 'warm-up' rows (NaNs)
        all_results.append(group[output_cols].dropna(subset=['rsi']))

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