import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates the Ultimate Oscillator (UO).
    UO = 100 * [(4 * Avg7) + (2 * Avg14) + Avg28] / (4 + 2 + 1)
    Avg_n = Sum(BuyingPressure_n) / Sum(TrueRange_n)
    """

    # 1. Parse Parameters
    try:
        p1 = int(options.get('p1', 7))
        p2 = int(options.get('p2', 14))
        p3 = int(options.get('p3', 28))
    except (ValueError, TypeError):
        p1, p2, p3 = 7, 14, 28

    if not data:
        return [[], []]

    # 2. Determine Price Precision
    try:
        sample_price = str(data[0].get('close', '0.00000'))
        precision = len(sample_price.split('.')[1]) if '.' in sample_price else 2
    except (IndexError, AttributeError):
        precision = 2

    # 3. Prepare DataFrame
    df = pd.DataFrame(data)
    is_mt4 = options.get('mt4') is True
    
    # 4. Dynamic Column Mapping
    if is_mt4:
        output_cols = ['date', 'time', 'uo']
        sort_cols = ['date', 'time']
    else:
        output_cols = ['symbol', 'timeframe', 'time', 'uo']
        sort_cols = ['time']

    # 5. Calculation Logic
    all_results = []
    group_keys = ['symbol', 'timeframe'] if not is_mt4 else None
    grouped = df.groupby(group_keys) if group_keys else [(None, df)]

    for _, group in grouped:
        group = group.sort_values(sort_cols).reset_index(drop=True)
        
        # Calculate Buying Pressure (BP) and True Range (TR)
        prev_close = group['close'].shift(1)
        min_low_prevclose = pd.concat([group['low'], prev_close], axis=1).min(axis=1)
        max_high_prevclose = pd.concat([group['high'], prev_close], axis=1).max(axis=1)
        
        bp = group['close'] - min_low_prevclose
        tr = max_high_prevclose - min_low_prevclose
        
        # Average calculations for 3 periods
        def get_avg(period):
            return bp.rolling(window=period).sum() / tr.rolling(window=period).sum()
        
        avg1 = get_avg(p1)
        avg2 = get_avg(p2)
        avg3 = get_avg(p3)
        
        # Ultimate Oscillator Formula
        group['uo'] = 100 * ((4 * avg1) + (2 * avg2) + avg3) / (4 + 2 + 1)

        # 6. Apply Dynamic Rounding
        group['uo'] = group['uo'].round(precision)
        
        # 7. Filter and Collect (Drop rows based on longest period)
        all_results.append(group[output_cols].dropna(subset=['uo']))

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