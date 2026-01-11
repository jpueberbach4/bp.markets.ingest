import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates the Rate of Change (ROC) indicator.
    Formula: ((Current Price - Price n periods ago) / Price n periods ago) * 100
    Supports standard OHLCV and MT4 (split date/time) formats with dynamic rounding.
    """

    # 1. Parse Parameters
    try:
        period = int(options.get('period', 12))
    except (ValueError, TypeError):
        period = 12

    if not data:
        return [[], []]

    # 2. Determine Price Precision for Rounding
    # Detects decimals from the first available close price to round output
    try:
        sample_price = str(data[0].get('close', '0.00000'))
        precision = len(sample_price.split('.')[1]) if '.' in sample_price else 2
    except (IndexError, AttributeError):
        precision = 3 # Default to 3 for momentum oscillators if detection fails

    # 3. Prepare DataFrame
    df = pd.DataFrame(data)
    is_mt4 = options.get('mt4') is True
    
    # 4. Dynamic Column Mapping
    if is_mt4:
        output_cols = ['date', 'time', 'roc']
        sort_cols = ['date', 'time']
    else:
        output_cols = ['symbol', 'timeframe', 'time', 'roc']
        sort_cols = ['time']

    # Ensure numeric conversion
    df['close'] = pd.to_numeric(df['close'], errors='coerce')
    
    all_results = []
    group_keys = ['symbol', 'timeframe'] if not is_mt4 else None
    grouped = df.groupby(group_keys) if group_keys else [(None, df)]

    for _, group in grouped:
        # Sort chronologically for shifting (crucial for "price n periods ago")
        group = group.sort_values(sort_cols).reset_index(drop=True)
        
        # 5. Calculation Logic
        # ROC = ((Price - Price_n) / Price_n) * 100
        price_n = group['close'].shift(period)
        group['roc'] = ((group['close'] - price_n) / price_n.replace(0, np.nan)) * 100

        # 6. Apply Dynamic Rounding
        # Uses detected precision or fixed 3-decimal precision for percentage values
        group['roc'] = group['roc'].round(precision)
        
        # 7. Cleanup
        # Drop warm-up rows where price_n was not yet available
        all_results.append(group[output_cols].dropna(subset=['roc']))

    if not all_results:
        return [output_cols, []]

    # 8. Final Formatting
    final_df = pd.concat(all_results)
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by=sort_cols, ascending=is_asc)
    
    # FINAL SAFETY GATE (JSON COMPLIANCE)
    # Replaces any stray NaN/Inf with None (null in JSON)
    data_as_list = final_df.values.tolist()
    clean_data = [
        [(x if (not isinstance(x, (float, np.floating)) or np.isfinite(x)) else None) for x in row]
        for row in data_as_list
    ]
    
    return [output_cols, clean_data]