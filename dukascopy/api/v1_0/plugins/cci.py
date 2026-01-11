import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates the Commodity Channel Index (CCI).
    Formula: (Typical Price - SMA of TP) / (0.015 * Mean Deviation)
    """

    # 1. Parse Parameters
    try:
        period = int(options.get('period', 20))
    except (ValueError, TypeError):
        period = 20

    if not data:
        return [[], []]

    # 2. Prepare DataFrame
    df = pd.DataFrame(data)
    is_mt4 = options.get('mt4') is True
    
    if is_mt4:
        output_cols = ['date', 'time', 'cci', 'direction']
        sort_cols = ['date', 'time']
    else:
        output_cols = ['symbol', 'timeframe', 'time', 'cci', 'direction']
        sort_cols = ['time']

    # Ensure numeric conversion
    for col in ['high', 'low', 'close']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    all_results = []
    group_keys = ['symbol', 'timeframe'] if not is_mt4 else None
    grouped = df.groupby(group_keys) if group_keys else [(None, df)]

    for _, group in grouped:
        group = group.sort_values(sort_cols).reset_index(drop=True)
        
        # 3. Calculate Typical Price (TP)
        tp = (group['high'] + group['low'] + group['close']) / 3
        
        # 4. Calculate SMA of Typical Price
        tp_sma = tp.rolling(window=period).mean()
        
        # 5. Calculate Mean Deviation
        # Standard CCI uses the average of absolute differences from the SMA
        def get_mad(x):
            return np.abs(x - x.mean()).mean()
        
        mad = tp.rolling(window=period).apply(get_mad, raw=True)

        # 6. Calculate CCI
        # Constant 0.015 is used to ensure 70-80% of values fall between -100 and +100
        group['cci'] = (tp - tp_sma) / (0.015 * mad)
        
        # Directional slope for UI/Logic
        group['direction'] = np.where(group['cci'] > group['cci'].shift(1), 1, -1)

        # 7. Cleanup
        group_clean = group.iloc[period:].copy()
        all_results.append(group_clean[output_cols])

    if not all_results:
        return [output_cols, []]

    final_df = pd.concat(all_results)
    
    # Sort results
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by=sort_cols, ascending=is_asc)
    
    # FINAL SAFETY GATE (JSON COMPLIANCE)
    data_as_list = final_df.values.tolist()
    clean_data = [
        [ (x if (isinstance(x, (float, np.floating)) and np.isfinite(x)) else x) for x in row ]
        for row in data_as_list
    ]
    
    return [output_cols, clean_data]