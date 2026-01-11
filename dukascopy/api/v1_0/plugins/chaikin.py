import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates Chaikin Oscillator.
    Handles zero-volume or flat-bar scenarios to prevent constant zero output.
    """

    # 1. Parse Parameters
    try:
        short_period = int(options.get('short', 3))
        long_period = int(options.get('long', 10))
    except (ValueError, TypeError):
        short_period, long_period = 3, 10

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
        output_cols = ['date', 'time', 'chaikin']
        sort_cols = ['date', 'time']
    else:
        output_cols = ['symbol', 'timeframe', 'time', 'chaikin']
        sort_cols = ['time']

    # 5. Calculation Logic
    all_results = []
    group_keys = ['symbol', 'timeframe'] if not is_mt4 else ['symbol']
    
    if 'symbol' not in df.columns: df['symbol'] = 'N/A'
    if 'timeframe' not in df.columns and not is_mt4: df['timeframe'] = 'N/A'

    grouped = df.groupby(group_keys)

    for _, group in grouped:
        group = group.sort_values(sort_cols).reset_index(drop=True)
        
        # A. Calculate Money Flow Multiplier
        # Use replace to avoid division by zero on flat bars
        range_high_low = (group['high'] - group['low']).replace(0, np.nan)
        mfm = ((group['close'] - group['low']) - (group['high'] - group['close'])) / range_high_low
        
        # Fill NaN values from flat bars with 0
        mfm = mfm.fillna(0)
        
        # B. Calculate Money Flow Volume
        mfv = mfm * group['volume']
        
        # C. Calculate ADL (Accumulation Distribution Line)
        adl = mfv.cumsum()
        
        # D. Chaikin Oscillator = EMA(ADL, short) - EMA(ADL, long)
        ema_short = adl.ewm(span=short_period, adjust=False).mean()
        ema_long = adl.ewm(span=long_period, adjust=False).mean()
        
        group['chaikin'] = ema_short - ema_long

        # 6. Apply Dynamic Rounding
        group['chaikin'] = group['chaikin'].round(precision)
        
        # 7. Collect Results
        all_results.append(group[output_cols])

    if not all_results:
        return [output_cols, []]

    # 8. Final Formatting
    final_df = pd.concat(all_results)
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by=sort_cols, ascending=is_asc)

    columns = list(final_df.columns)
    values = final_df.replace({np.nan: None, np.inf: None, -np.inf: None}).values.tolist()

    return [columns, values]