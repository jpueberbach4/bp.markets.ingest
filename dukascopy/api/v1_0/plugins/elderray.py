import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates Elder Ray Index (Bull Power and Bear Power).
    Bull Power = High - EMA
    Bear Power = Low - EMA
    Supports standard OHLCV and MT4 (split date/time) formats.
    """

    # 1. Parse Parameters (Default period is 13 as per Dr. Elder)
    try:
        period = int(options.get('period', 13))
    except (ValueError, TypeError):
        period = 13

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
        output_cols = ['date', 'time', 'bull_power', 'bear_power']
        sort_cols = ['date', 'time']
    else:
        output_cols = ['symbol', 'timeframe', 'time', 'bull_power', 'bear_power']
        sort_cols = ['time']

    # 5. Group and Calculate
    all_results = []
    group_keys = ['symbol', 'timeframe'] if not is_mt4 else ['symbol']
    
    if 'symbol' not in df.columns:
        df['symbol'] = 'N/A'
    if 'timeframe' not in df.columns and not is_mt4:
        df['timeframe'] = 'N/A'

    grouped = df.groupby(group_keys)

    for _, group in grouped:
        group = group.sort_values(sort_cols).reset_index(drop=True)
        
        # A. Calculate EMA (Baseline)
        ema = group['close'].ewm(span=period, adjust=False).mean()
        
        # B. Calculate Power Components
        group['bull_power'] = group['high'] - ema
        group['bear_power'] = group['low'] - ema
        
        # 6. Apply Dynamic Rounding
        group['bull_power'] = group['bull_power'].round(precision)
        group['bear_power'] = group['bear_power'].round(precision)
        
        # 7. Filter and Collect (Drop warm-up rows where EMA is stabilizing)
        all_results.append(group[output_cols].iloc[period-1:])

    if not all_results:
        return [output_cols, []]

    # 8. Final Formatting
    final_df = pd.concat(all_results)
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by=sort_cols, ascending=is_asc)

    # Final safety gate for JSON compatibility (handles NaN/Inf)
    columns = list(final_df.columns)
    values = final_df.replace({np.nan: None, np.inf: None, -np.inf: None}).values.tolist()

    return [columns, values]