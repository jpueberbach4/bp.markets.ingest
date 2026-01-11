import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates Money Flow Index (MFI).
    MFI = 100 - (100 / (1 + Money Flow Ratio))
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
    # Detects decimals from the first available close price to round output
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
        output_cols = ['date', 'time', 'mfi']
        sort_cols = ['date', 'time']
    else:
        output_cols = ['symbol', 'timeframe', 'time', 'mfi']
        sort_cols = ['time']

    # Ensure numeric types
    for col in ['high', 'low', 'close', 'volume']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    all_results = []
    group_keys = ['symbol', 'timeframe'] if not is_mt4 else None
    grouped = df.groupby(group_keys) if group_keys else [(None, df)]

    for _, group in grouped:
        # Sort by the appropriate time columns
        group = group.sort_values(sort_cols).reset_index(drop=True)
        
        # 5. Calculation Logic
        # A. Calculate Typical Price
        tp = (group['high'] + group['low'] + group['close']) / 3
        
        # B. Calculate Raw Money Flow
        rmf = tp * group['volume']
        
        # C. Determine Positive and Negative Money Flow
        tp_shift = tp.shift(1)
        pos_mf = rmf.where(tp > tp_shift, 0)
        neg_mf = rmf.where(tp < tp_shift, 0)
        
        # D. Calculate Money Flow Ratio
        mfr_pos = pos_mf.rolling(window=period).sum()
        mfr_neg = neg_mf.rolling(window=period).sum()
        
        mf_ratio = mfr_pos / mfr_neg.replace(0, np.nan)
        
        # E. Calculate MFI
        group['mfi'] = 100 - (100 / (1 + mf_ratio))
        
        # 6. Apply Dynamic Rounding
        # Rounds MFI to match asset price precision
        group['mfi'] = group['mfi'].round(precision)
        
        # 7. Filter and Collect
        # Drop warm-up rows where MFI is NaN
        all_results.append(group[output_cols].dropna(subset=['mfi']))

    if not all_results:
        return [output_cols, []]

    # 8. Final Formatting
    final_df = pd.concat(all_results)
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