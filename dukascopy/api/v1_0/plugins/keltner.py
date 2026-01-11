import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates Keltner Channels.
    Middle Line: EMA (default 20)
    Bands: Middle Line +/- (Multiplier * ATR)
    Supports standard OHLCV and MT4 (split date/time) formats with dynamic rounding.
    """

    # 1. Parse Parameters
    try:
        ema_period = int(options.get('period', 20))
        atr_period = int(options.get('atr_period', 10))
        multiplier = float(options.get('multiplier', 2.0))
    except (ValueError, TypeError):
        ema_period, atr_period, multiplier = 20, 10, 2.0

    if not data:
        return [[], []]

    # 2. Determine Price Precision
    # Detects decimals from the first available close price to round output levels
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
        output_cols = ['date', 'time', 'upper', 'mid', 'lower']
        sort_cols = ['date', 'time']
    else:
        output_cols = ['symbol', 'timeframe', 'time', 'upper', 'mid', 'lower']
        sort_cols = ['time']

    for col in ['high', 'low', 'close']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    all_results = []
    group_keys = ['symbol', 'timeframe'] if not is_mt4 else None
    grouped = df.groupby(group_keys) if group_keys else [(None, df)]

    for _, group in grouped:
        group = group.sort_values(sort_cols).reset_index(drop=True)
        
        # 5. Calculation Logic
        # A. Middle Line (EMA)
        group['mid'] = group['close'].ewm(span=ema_period, adjust=False).mean()
        
        # B. Calculate ATR (Wilder's Smoothing)
        prev_close = group['close'].shift(1)
        tr1 = group['high'] - group['low']
        tr2 = (group['high'] - prev_close).abs()
        tr3 = (group['low'] - prev_close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # Wilder's Smoothing for ATR
        atr = tr.ewm(alpha=1/atr_period, min_periods=atr_period).mean()
        
        # C. Calculate Bands
        group['upper'] = group['mid'] + (multiplier * atr)
        group['lower'] = group['mid'] - (multiplier * atr)
        
        # 6. Apply Dynamic Rounding
        # Rounds all band levels to match the asset's price precision
        for col in ['upper', 'mid', 'lower']:
            group[col] = group[col].round(precision)
        
        # 7. Cleanup and Collect
        # Drop warm-up rows based on the longer of the two periods
        warmup = max(ema_period, atr_period)
        all_results.append(group[output_cols].iloc[warmup:])

    if not all_results:
        return [output_cols, []]

    # 8. Final Formatting
    final_df = pd.concat(all_results)
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by=sort_cols, ascending=is_asc)
    
    # FINAL SAFETY GATE (JSON COMPLIANCE)
    # Handles non-finite numbers like NaN or Inf
    data_as_list = final_df.values.tolist()
    clean_data = [
        [(x if (isinstance(x, (float, np.floating)) and np.isfinite(x)) else x) for x in row]
        for row in data_as_list
    ]
    
    return [output_cols, clean_data]