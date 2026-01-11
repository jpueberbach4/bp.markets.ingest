import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates the Accumulation/Distribution Line (ADL).
    1. Money Flow Multiplier = [(Close - Low) - (High - Close)] / (High - Low)
    2. Money Flow Volume = Money Flow Multiplier * Volume
    3. ADL = Previous ADL + Current Money Flow Volume
    """

    if not data:
        return [[], []]

    # 1. Determine Price Precision
    try:
        sample_price = str(data[0].get('close', '0.00000'))
        precision = len(sample_price.split('.')[1]) if '.' in sample_price else 2
    except (IndexError, AttributeError):
        precision = 2

    # 2. Prepare DataFrame
    df = pd.DataFrame(data)
    is_mt4 = options.get('mt4') is True
    
    # 3. Dynamic Column Mapping
    if is_mt4:
        output_cols = ['date', 'time', 'adl']
        sort_cols = ['date', 'time']
    else:
        output_cols = ['symbol', 'timeframe', 'time', 'adl']
        sort_cols = ['time']

    # 4. Calculation Logic
    all_results = []
    group_keys = ['symbol', 'timeframe'] if not is_mt4 else ['symbol']
    
    if 'symbol' not in df.columns: df['symbol'] = 'N/A'
    if 'timeframe' not in df.columns and not is_mt4: df['timeframe'] = 'N/A'

    grouped = df.groupby(group_keys)

    for _, group in grouped:
        group = group.sort_values(sort_cols).reset_index(drop=True)
        
        # A. Money Flow Multiplier (MFM)
        # Handle division by zero for flat bars (High == Low)
        h_l_range = (group['high'] - group['low']).replace(0, np.nan)
        mfm = ((group['close'] - group['low']) - (group['high'] - group['close'])) / h_l_range
        
        # Fill NaN values (from flat bars) with 0
        mfm = mfm.fillna(0)
        
        # B. Money Flow Volume (MFV)
        mfv = mfm * group['volume']
        
        # C. Accumulation/Distribution Line (Cumulative Sum)
        group['adl'] = mfv.cumsum()

        # 5. Apply Dynamic Rounding
        # ADL values can be very large due to volume, but we round the result
        group['adl'] = group['adl'].round(precision)
        
        # 6. Collect Results
        all_results.append(group[output_cols])

    if not all_results:
        return [output_cols, []]

    # 7. Final Formatting
    final_df = pd.concat(all_results)
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by=sort_cols, ascending=is_asc)

    # Convert to JSON-ready list of lists
    columns = list(final_df.columns)
    values = final_df.replace({np.nan: None, np.inf: None, -np.inf: None}).values.tolist()

    return [columns, values]