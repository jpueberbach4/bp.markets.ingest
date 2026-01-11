import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates Hull Moving Average (HMA).
    Formula: WMA(2*WMA(n/2) - WMA(n), sqrt(n))
    Supports standard OHLCV and MT4 (split date/time) formats with dynamic rounding.
    """

    # 1. Parse Parameters
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14

    if not data:
        return [[], []]

    # 2. Determine Price Precision
    # Detects decimals from the first available close price to round the HMA output
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
        output_cols = ['date', 'time', 'hma']
        sort_cols = ['date', 'time']
    else:
        output_cols = ['symbol', 'timeframe', 'time', 'hma']
        sort_cols = ['time']

    # Ensure numeric conversion
    df['close'] = pd.to_numeric(df['close'], errors='coerce')
    
    all_results = []
    group_keys = ['symbol', 'timeframe'] if not is_mt4 else None
    grouped = df.groupby(group_keys) if group_keys else [(None, df)]

    for _, group in grouped:
        # Sort by the appropriate time columns
        group = group.sort_values(sort_cols).reset_index(drop=True)
        
        # Helper for Weighted Moving Average
        def wma(series, n):
            weights = np.arange(1, n + 1)
            return series.rolling(n).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True)

        # 5. Calculation Logic
        half_period = int(period / 2)
        sqrt_period = int(np.sqrt(period))

        # Formula: 2 * WMA(n/2) - WMA(n)
        raw_hma = (2 * wma(group['close'], half_period)) - wma(group['close'], period)
        
        # Final smoothing: WMA(raw_hma, sqrt(n))
        group['hma'] = wma(raw_hma, sqrt_period)
        
        # 6. Apply Dynamic Rounding
        # Rounds the HMA values to match the asset's price precision
        group['hma'] = group['hma'].round(precision)
        
        # 7. Cleanup and Collect
        # Drop warm-up rows (where HMA is NaN)
        all_results.append(group[output_cols].dropna(subset=['hma']))

    if not all_results:
        return [output_cols, []]

    # 8. Final Formatting
    final_df = pd.concat(all_results)
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