import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates Heikin Ashi Candlesticks.
    Formula:
    - Close = (Open + High + Low + Close) / 4
    - Open = (Prev_HA_Open + Prev_HA_Close) / 2
    - High = Max(High, HA_Open, HA_Close)
    - Low = Min(Low, HA_Open, HA_Close)
    """

    if not data:
        return [[], []]

    # 1. Determine Price Precision
    try:
        sample_price = str(data[0].get('close', '0.00000'))
        precision = len(sample_price.split('.')[1]) if '.' in sample_price else 2
    except (IndexError, AttributeError):
        precision = 5

    # 2. Prepare DataFrame
    df = pd.DataFrame(data)
    is_mt4 = options.get('mt4') is True
    
    # 3. Dynamic Column Mapping
    if is_mt4:
        output_cols = ['date', 'time', 'ha_open', 'ha_high', 'ha_low', 'ha_close']
        sort_cols = ['date', 'time']
    else:
        output_cols = ['symbol', 'timeframe', 'time', 'ha_open', 'ha_high', 'ha_low', 'ha_close']
        sort_cols = ['time']

    all_results = []
    group_keys = ['symbol', 'timeframe'] if not is_mt4 else None
    grouped = df.groupby(group_keys) if group_keys else [(None, df)]

    for _, group in grouped:
        group = group.sort_values(sort_cols).reset_index(drop=True)
        
        # A. Calculate HA Close (Simple Average)
        ha_close = (group['open'] + group['high'] + group['low'] + group['close']) / 4
        
        # B. Calculate HA Open (Iterative process)
        ha_open = np.zeros(len(group))
        # Initial HA Open uses the average of the first real candle's open/close
        ha_open[0] = (group.loc[0, 'open'] + group.loc[0, 'close']) / 2
        
        for i in range(1, len(group)):
            ha_open[i] = (ha_open[i-1] + ha_close[i-1]) / 2
            
        group['ha_open'] = ha_open
        group['ha_close'] = ha_close
        
        # C. Calculate HA High and Low
        group['ha_high'] = group[['high', 'ha_open', 'ha_close']].max(axis=1)
        group['ha_low'] = group[['low', 'ha_open', 'ha_close']].min(axis=1)

        # 4. Apply Dynamic Rounding
        for col in ['ha_open', 'ha_high', 'ha_low', 'ha_close']:
            group[col] = group[col].round(precision)
        
        all_results.append(group[output_cols])

    if not all_results:
        return [output_cols, []]

    # 5. Final Formatting
    final_df = pd.concat(all_results)
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by=sort_cols, ascending=is_asc)
    
    return [output_cols, final_df.values.tolist()]