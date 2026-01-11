import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates Volume-Weighted Average Price (VWAP) per Symbol/Timeframe.
    Supports standard OHLCV and MT4 (split date/time) formats.
    """

    if not data:
        return [[], []]

    # 1. Prepare DataFrame
    df = pd.DataFrame(data)
    
    # Detect MT4 mode
    is_mt4 = options.get('mt4') is True
    
    # 2. Dynamic Column Mapping
    # If MT4 is True, system returns 'date' and 'time' strings separately
    if is_mt4:
        output_cols = ['date', 'time', 'vwap']
        sort_cols = ['date', 'time']
    else:
        output_cols = ['symbol', 'timeframe', 'time', 'vwap']
        sort_cols = ['time']

    # 3. Ensure numeric types for calculation
    # VWAP requires High, Low, Close, and Volume
    for col in ['high', 'low', 'close', 'volume']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    all_results = []

    # 4. Group and Calculate
    # MT4 queries are restricted to a single selection in routes.py
    group_keys = ['symbol', 'timeframe'] if not is_mt4 else None

    if group_keys:
        grouped = df.groupby(group_keys)
    else:
        grouped = [(None, df)]

    for _, group in grouped:
        # Sort chronologically for cumulative sum accuracy
        group = group.sort_values(sort_cols)
        
        # A. Calculate Typical Price
        typical_price = (group['high'] + group['low'] + group['close']) / 3
        
        # B. Calculate Cumulative Totals
        # PV = Typical Price * Volume
        cum_pv = (typical_price * group['volume']).cumsum()
        cum_vol = group['volume'].cumsum()
        
        # C. Calculate VWAP
        # Handle potential division by zero if volume is missing
        group['vwap'] = cum_pv / cum_vol.replace(0, np.nan)
        
        # Drop rows where volume was 0/NaN resulting in NaN VWAP
        all_results.append(group[output_cols].dropna(subset=['vwap']))

    if not all_results:
        return [output_cols, []]

    # 5. Final Formatting
    final_df = pd.concat(all_results)
    
    # Apply user-requested sort order
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by=sort_cols, ascending=is_asc)
    
    return [output_cols, final_df.values.tolist()]