import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates Volume-Weighted Average Price (VWAP) per Symbol/Timeframe.
    Supports standard OHLCV and MT4 (split date/time) formats with dynamic rounding.
    """

    if not data:
        return [[], []]

    # 1. Determine Price Precision
    # Detects decimals from the first available close price to round output
    try:
        sample_price = str(data[0].get('close', '0.00000'))
        precision = len(sample_price.split('.')[1]) if '.' in sample_price else 2
    except (IndexError, AttributeError):
        precision = 5

    # 2. Prepare DataFrame
    df = pd.DataFrame(data)
    
    # Detect MT4 mode
    is_mt4 = options.get('mt4') is True
    
    # 3. Dynamic Column Mapping
    if is_mt4:
        output_cols = ['date', 'time', 'vwap']
        sort_cols = ['date', 'time']
    else:
        output_cols = ['symbol', 'timeframe', 'time', 'vwap']
        sort_cols = ['time']

    # Ensure numeric types for calculation
    # VWAP requires High, Low, Close, and Volume
    for col in ['high', 'low', 'close', 'volume']:\
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    all_results = []

    # 4. Group and Calculate
    group_keys = ['symbol', 'timeframe'] if not is_mt4 else None
    grouped = df.groupby(group_keys) if group_keys else [(None, df)]

    for _, group in grouped:
        # Sort chronologically for cumulative sum accuracy
        group = group.sort_values(sort_cols).reset_index(drop=True)
        
        # A. Calculate Typical Price
        typical_price = (group['high'] + group['low'] + group['close']) / 3
        
        # B. Calculate Cumulative Totals
        # PV = Typical Price * Volume
        cum_pv = (typical_price * group['volume']).cumsum()
        cum_vol = group['volume'].cumsum()
        
        # C. Calculate VWAP
        # Handle potential division by zero if volume is missing
        group['vwap'] = cum_pv / cum_vol.replace(0, np.nan)
        
        # 5. Apply Dynamic Rounding
        # Rounds the VWAP values to match the asset's price precision
        group['vwap'] = group['vwap'].round(precision)
        
        # Drop rows where volume was 0/NaN resulting in NaN VWAP
        all_results.append(group[output_cols].dropna(subset=['vwap']))

    if not all_results:
        return [output_cols, []]

    # 6. Final Formatting
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