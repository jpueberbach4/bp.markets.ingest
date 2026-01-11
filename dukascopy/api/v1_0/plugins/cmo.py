import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates Chande Momentum Oscillator (CMO).
    CMO = 100 * ((Sum of Gains - Sum of Losses) / (Sum of Gains + Sum of Losses))
    Supports standard OHLCV and MT4 (split date/time) formats with dynamic rounding.
    """

    # 1. Parse Parameters
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14

    if not data:
        return [[], []]

    # 2. Determine Price Precision for Rounding
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
        output_cols = ['date', 'time', 'cmo']
        sort_cols = ['date', 'time']
    else:
        output_cols = ['symbol', 'timeframe', 'time', 'cmo']
        sort_cols = ['time']

    # 5. Group and Calculate CMO
    all_results = []
    group_keys = ['symbol', 'timeframe'] if not is_mt4 else ['symbol']
    
    # Ensure symbol exists for grouping if not in MT4 mode
    if 'symbol' not in df.columns:
        df['symbol'] = 'N/A'
    if 'timeframe' not in df.columns and not is_mt4:
        df['timeframe'] = 'N/A'

    grouped = df.groupby(group_keys)

    for _, group in grouped:
        group = group.sort_values(sort_cols).reset_index(drop=True)
        
        # A. Calculate Price Change
        delta = group['close'].diff()
        
        # B. Identify Gains and Losses
        gains = delta.where(delta > 0, 0)
        losses = delta.where(delta < 0, 0).abs()
        
        # C. Calculate Rolling Sums
        sum_gains = gains.rolling(window=period).sum()
        sum_losses = losses.rolling(window=period).sum()
        
        # D. Calculate CMO
        # Formula: 100 * (SumG - SumL) / (SumG + SumL)
        total_movement = sum_gains + sum_losses
        group['cmo'] = 100 * ((sum_gains - sum_losses) / total_movement.replace(0, np.nan))
        
        # 6. Apply Dynamic Rounding
        group['cmo'] = group['cmo'].round(precision)
        
        # 7. Filter and Collect
        # Drop rows where CMO is NaN (the warm-up period)
        all_results.append(group[output_cols].dropna(subset=['cmo']))

    if not all_results:
        return [output_cols, []]

    # 8. Final Formatting
    final_df = pd.concat(all_results)
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by=sort_cols, ascending=is_asc)

    # Convert to JSON-ready list of lists
    columns = list(final_df.columns)
    values = final_df.replace({np.nan: None, np.inf: None, -np.inf: None}).values.tolist()

    return [columns, values]