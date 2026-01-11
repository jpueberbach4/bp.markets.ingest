import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates On-Balance Volume (OBV).
    Formula: Cumulative sum of (+Volume if Close > PrevClose, -Volume if Close < PrevClose)
    """

    if not data:
        return [[], []]

    # 1. Prepare DataFrame
    df = pd.DataFrame(data)
    is_mt4 = options.get('mt4') is True
    
    # 2. Dynamic Column Mapping
    if is_mt4:
        output_cols = ['date', 'time', 'obv']
        sort_cols = ['date', 'time']
    else:
        output_cols = ['symbol', 'timeframe', 'time', 'obv']
        sort_cols = ['time']

    # Ensure numeric types for calculation
    df['close'] = pd.to_numeric(df['close'], errors='coerce')
    df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
    
    all_results = []
    group_keys = ['symbol', 'timeframe'] if not is_mt4 else None
    grouped = df.groupby(group_keys) if group_keys else [(None, df)]

    for _, group in grouped:
        # IMPORTANT: Sort ASCENDING for cumulative calculation
        group = group.sort_values(sort_cols).reset_index(drop=True)
        
        # 3. OBV Calculation Logic
        close_diff = group['close'].diff()
        
        # Determine direction: 1 for up, -1 for down, 0 for flat
        direction = np.where(close_diff > 0, 1, np.where(close_diff < 0, -1, 0))
        
        # Cumulative sum of Direction * Volume
        group['obv'] = (direction * group['volume']).cumsum()

        # 4. Corrected Rounding Logic
        # OBV represents VOLUME. We round to 2 decimals to preserve 
        # crypto volume precision (which often has fractions).
        group['obv'] = group['obv'].round(2)
        
        all_results.append(group[output_cols])

    if not all_results:
        return [output_cols, []]

    # 5. Final Formatting
    final_df = pd.concat(all_results)
    
    # Apply requested sort order (descending for your JSON)
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by=sort_cols, ascending=is_asc)
    
    # Handle NaN/Inf for JSON
    data_as_list = final_df.values.tolist()
    clean_data = [
        [(x if (not isinstance(x, (float, np.floating)) or np.isfinite(x)) else None) for x in row]
        for row in data_as_list
    ]
    
    return [output_cols, clean_data]