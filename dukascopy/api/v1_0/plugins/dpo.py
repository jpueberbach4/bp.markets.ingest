import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates Detrended Price Oscillator (DPO).
    Formula: Price( (n/2) + 1 periods ago) - SMA(n)
    Note: DPO is shifted back, so the most recent (n/2 + 1) bars will be NaN.
    """

    # 1. Parse Parameters
    try:
        period = int(options.get('period', 20))
    except (ValueError, TypeError):
        period = 20

    if not data:
        return [[], []]

    # 2. Determine Price Precision
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
        output_cols = ['date', 'time', 'dpo']
        sort_cols = ['date', 'time']
    else:
        output_cols = ['symbol', 'timeframe', 'time', 'dpo']
        sort_cols = ['time']

    # 5. Calculation Logic
    all_results = []
    group_keys = ['symbol', 'timeframe'] if not is_mt4 else None
    grouped = df.groupby(group_keys) if group_keys else [(None, df)]

    for _, group in grouped:
        group = group.sort_values(sort_cols).reset_index(drop=True)
        
        # Calculate SMA
        sma = group['close'].rolling(window=period).mean()
        
        # Shift back by (period / 2) + 1
        shift = int((period / 2) + 1)
        
        # DPO Formula
        group['dpo'] = group['close'].shift(shift) - sma

        # 6. Apply Dynamic Rounding
        group['dpo'] = group['dpo'].round(precision)
        
        # 7. Filter and Collect (DPO has significant lead-in/warm-up time)
        all_results.append(group[output_cols].dropna(subset=['dpo']))

    if not all_results:
        return [output_cols, []]

    # 8. Final Formatting
    final_df = pd.concat(all_results)
    
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by=sort_cols, ascending=is_asc)
    
    # Final safety gate for JSON compatibility
    data_as_list = final_df.values.tolist()
    clean_data = [
        [(x if (not isinstance(x, (float, np.floating)) or np.isfinite(x)) else None) for x in row]
        for row in data_as_list
    ]
    
    return [output_cols, clean_data]