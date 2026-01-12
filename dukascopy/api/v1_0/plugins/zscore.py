import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates the Z-Score (Standard Score).
    Formula: Z = (Current Price - Mean) / Standard Deviation
    A Z-Score of 0 is the mean; +2.0 or -2.0 are typical exhaustion levels.
    """

    # 1. Parse Period
    try:
        period = int(options.get('period', 20))
    except (ValueError, TypeError):
        period = 20

    if not data:
        return [[], []]

    # 2. Determine Precision
    # Z-score is a statistical ratio, usually represented with 2-3 decimals
    precision = 3

    # 3. Prepare DataFrame
    df = pd.DataFrame(data)
    is_mt4 = options.get('mt4') is True
    
    # 4. Dynamic Column Mapping
    if is_mt4:
        output_cols = ['date', 'time', 'z_score', 'direction']
        sort_cols = ['date', 'time']
    else:
        output_cols = ['symbol', 'timeframe', 'time', 'z_score', 'direction']
        sort_cols = ['time']

    all_results = []
    group_keys = ['symbol', 'timeframe'] if not is_mt4 else None
    grouped = df.groupby(group_keys) if group_keys else [(None, df)]

    for _, group in grouped:
        group = group.sort_values(sort_cols).reset_index(drop=True)
        
        # A. Calculate Mean (SMA)
        mean = group['close'].rolling(window=period).mean()
        
        # B. Calculate Standard Deviation
        std_dev = group['close'].rolling(window=period).std()
        
        # C. Calculate Z-Score
        # Avoid division by zero for flat markets
        group['z_score'] = (group['close'] - mean) / std_dev.replace(0, np.nan)
        
        # D. Directional slope (is the score increasing or decreasing?)
        group['direction'] = np.where(group['z_score'] > group['z_score'].shift(1), 1, -1)

        # 5. Apply Rounding
        group['z_score'] = group['z_score'].round(precision)
        
        # 6. Filter and Collect
        all_results.append(group[output_cols].dropna(subset=['z_score']))

    if not all_results:
        return [output_cols, []]

    # 7. Final Formatting
    final_df = pd.concat(all_results)
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by=sort_cols, ascending=is_asc)
    
    return [output_cols, final_df.values.tolist()]