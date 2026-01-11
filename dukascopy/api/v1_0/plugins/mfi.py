import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates Money Flow Index (MFI).
    MFI = 100 - (100 / (1 + Money Flow Ratio))
    Default period: 14
    """

    # 1. Parse Parameters
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14

    if not data:
        return [[], []]

    # 2. Prepare DataFrame
    df = pd.DataFrame(data)
    is_mt4 = options.get('mt4') is True
    
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
        group = group.sort_values(sort_cols)
        
        # A. Calculate Typical Price
        tp = (group['high'] + group['low'] + group['close']) / 3
        
        # B. Calculate Raw Money Flow
        rmf = tp * group['volume']
        
        # C. Determine Positive and Negative Money Flow
        # Compare current typical price to previous typical price
        tp_shift = tp.shift(1)
        pos_mf = rmf.where(tp > tp_shift, 0)
        neg_mf = rmf.where(tp < tp_shift, 0)
        
        # D. Calculate Money Flow Ratio
        mfr_pos = pos_mf.rolling(window=period).sum()
        mfr_neg = neg_mf.rolling(window=period).sum()
        
        mf_ratio = mfr_pos / mfr_neg.replace(0, np.nan)
        
        # E. Calculate MFI
        group['mfi'] = 100 - (100 / (1 + mf_ratio))
        
        # Drop warm-up rows
        all_results.append(group[output_cols].dropna(subset=['mfi']))

    if not all_results:
        return [output_cols, []]

    final_df = pd.concat(all_results)
    
    # Sort results
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by=sort_cols, ascending=is_asc)
    
    # Final JSON compliance cleanup
    final_df = final_df.replace([np.inf, -np.inf], np.nan)
    result_list = final_df.where(pd.notnull(final_df), None).values.tolist()
    
    return [output_cols, result_list]