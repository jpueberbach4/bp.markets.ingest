import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates Ichimoku Cloud components.
    Default Settings: 9, 26, 52
    """

    # 1. Parse Parameters
    try:
        tenkan_p = int(options.get('tenkan', 9))
        kijun_p = int(options.get('kijun', 26))
        senkou_b_p = int(options.get('senkou_b', 52))
        displacement = int(options.get('displacement', 26))
    except (ValueError, TypeError):
        tenkan_p, kijun_p, senkou_b_p, displacement = 9, 26, 52, 26

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
        output_cols = ['date', 'time', 'tenkan', 'kijun', 'span_a', 'span_b', 'chikou']
        sort_cols = ['date', 'time']
    else:
        output_cols = ['symbol', 'timeframe', 'time', 'tenkan', 'kijun', 'span_a', 'span_b', 'chikou']
        sort_cols = ['time']

    for col in ['high', 'low', 'close']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    all_results = []
    group_keys = ['symbol', 'timeframe'] if not is_mt4 else None
    grouped = df.groupby(group_keys) if group_keys else [(None, df)]

    for _, group in grouped:
        group = group.sort_values(sort_cols).reset_index(drop=True)
        
        # 5. Calculation Logic
        # Tenkan-sen (Conversion Line): (9-period high + 9-period low) / 2
        nine_h = group['high'].rolling(window=tenkan_p).max()
        nine_l = group['low'].rolling(window=tenkan_p).min()
        group['tenkan'] = (nine_h + nine_l) / 2

        # Kijun-sen (Base Line): (26-period high + 26-period low) / 2
        twentysix_h = group['high'].rolling(window=kijun_p).max()
        twentysix_l = group['low'].rolling(window=kijun_p).min()
        group['kijun'] = (twentysix_h + twentysix_l) / 2

        # Senkou Span A (Leading Span A): Midpoint of Tenkan and Kijun, shifted forward
        span_a_raw = (group['tenkan'] + group['kijun']) / 2
        group['span_a'] = span_a_raw.shift(displacement)

        # Senkou Span B (Leading Span B): (52-period high + 52-period low) / 2, shifted forward
        fiftytwo_h = group['high'].rolling(window=senkou_b_p).max()
        fiftytwo_l = group['low'].rolling(window=senkou_b_p).min()
        span_b_raw = (fiftytwo_h + fiftytwo_l) / 2
        group['span_b'] = span_b_raw.shift(displacement)

        # Chikou Span (Lagging Span): Close price shifted back
        group['chikou'] = group['close'].shift(-displacement)

        # 6. Apply Dynamic Rounding
        for col in ['tenkan', 'kijun', 'span_a', 'span_b', 'chikou']:
            group[col] = group[col].round(precision)
        
        # 7. Cleanup
        # Dropping rows where the core trend lines aren't yet calculated
        all_results.append(group[output_cols].dropna(subset=['kijun']))

    if not all_results:
        return [output_cols, []]

    # 8. Final Formatting
    final_df = pd.concat(all_results)
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by=sort_cols, ascending=is_asc)
    
    # FINAL SAFETY GATE
    data_as_list = final_df.values.tolist()
    clean_data = [
        [(x if (not isinstance(x, (float, np.floating)) or np.isfinite(x)) else None) for x in row]
        for row in data_as_list
    ]
    
    return [output_cols, clean_data]