import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates the Schaff Trend Cycle (STC).
    Formula: EMA smoothed double-stochastic of MACD.
    Supports standard OHLCV and MT4 (split date/time) formats with dynamic rounding.
    """

    # 1. Parse Parameters
    try:
        cycle = int(options.get('cycle', 10))
        fast = int(options.get('fast', 23))
        slow = int(options.get('slow', 50))
    except (ValueError, TypeError):
        cycle, fast, slow = 10, 23, 50

    if not data:
        return [[], []]

    # 2. Determine Price Precision
    # Detects decimals from the first available close price to round output
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
        output_cols = ['date', 'time', 'stc', 'direction']
        sort_cols = ['date', 'time']
    else:
        output_cols = ['symbol', 'timeframe', 'time', 'stc', 'direction']
        sort_cols = ['time']

    # Ensure numeric conversion
    df['close'] = pd.to_numeric(df['close'], errors='coerce')
    
    all_results = []
    group_keys = ['symbol', 'timeframe'] if not is_mt4 else None
    grouped = df.groupby(group_keys) if group_keys else [(None, df)]

    for _, group in grouped:
        # Sort by temporal columns
        group = group.sort_values(sort_cols).reset_index(drop=True)
        
        # 5. Calculation Logic
        # A. Calculate MACD Line
        ema_fast = group['close'].ewm(span=fast, adjust=False).mean()
        ema_slow = group['close'].ewm(span=slow, adjust=False).mean()
        macd = ema_fast - ema_slow

        # Internal Stochastic Helper
        def get_stoch(series, length):
            low_min = series.rolling(window=length).min()
            high_max = series.rolling(window=length).max()
            denom = (high_max - low_min).replace(0, np.nan)
            return 100 * (series - low_min) / denom

        # B. First Smoothing (Stochastic of MACD)
        stoch_1 = get_stoch(macd, cycle).fillna(0)
        smooth_1 = stoch_1.ewm(span=cycle/2, adjust=False).mean()

        # C. Second Smoothing (Stochastic of first smooth)
        stoch_2 = get_stoch(smooth_1, cycle).fillna(0)
        group['stc'] = stoch_2.ewm(span=cycle/2, adjust=False).mean()

        # 6. Apply Dynamic Rounding
        group['stc'] = group['stc'].round(precision)
        
        # Directional slope for UI/Logic
        group['direction'] = np.where(group['stc'] > group['stc'].shift(1), 1, -1)
        
        # 7. Cleanup and Append
        # Drop initial rows where calculation hasn't stabilized (slow + cycle)
        warmup = slow + cycle
        group_clean = group.iloc[warmup:].copy()
        all_results.append(group_clean[output_cols])

    if not all_results:
        return [output_cols, []]

    # 8. Final Formatting
    final_df = pd.concat(all_results)
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by=sort_cols, ascending=is_asc)
    
    # FINAL SAFETY GATE (JSON COMPLIANCE)
    data_as_list = final_df.values.tolist()
    clean_data = [
        [(x if (isinstance(x, (float, np.floating)) and np.isfinite(x)) else x) for x in row]
        for row in data_as_list
    ]
    
    return [output_cols, clean_data]