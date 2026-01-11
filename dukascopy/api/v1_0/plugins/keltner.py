import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates Keltner Channels.
    Middle Line: EMA (default 20)
    Bands: Middle Line +/- (Multiplier * ATR)
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

    # 2. Prepare DataFrame
    df = pd.DataFrame(data)
    is_mt4 = options.get('mt4') is True
    
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
        group = group.sort_values(sort_cols)
        
        # A. Calculate Middle Line (EMA)
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
        
        # Drop warm-up rows based on the longer of the two periods
        warmup = max(ema_period, atr_period)
        all_results.append(group[output_cols].iloc[warmup:])

    if not all_results:
        return [output_cols, []]

    final_df = pd.concat(all_results)
    
    # Sort results
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by=sort_cols, ascending=is_asc)
    
    # Final JSON compliance cleanup
    final_df = final_df.replace([np.inf, -np.inf], np.nan)
    result_list = final_df.where(pd.notnull(final_df), None).values.tolist()
    
    return [output_cols, result_list]