import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates Average Directional Index (ADX), +DI, and -DI.
    Supports standard OHLCV and MT4 (split date/time) formats.
    """

    # 1. Parse Period
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14

    options['period'] = str(period)

    if not data:
        return [[], []]

    # 2. Prepare DataFrame
    df = pd.DataFrame(data)
    
    # Detect MT4 mode based on configuration
    is_mt4 = options.get('mt4') is True
    
    # 3. Dynamic Column Mapping
    # When MT4 is active, helper.py selects separate date and time columns
    if is_mt4:
        output_cols = ['date', 'time', 'adx', 'plus_di', 'minus_di']
        sort_cols = ['date', 'time']
    else:
        output_cols = ['symbol', 'timeframe', 'time', 'adx', 'plus_di', 'minus_di']
        sort_cols = ['time']

    # Convert numeric columns for calculation
    for col in ['close', 'high', 'low']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    all_results = []

    # 4. Group and Calculate
    # routes.py restricts MT4 to single symbol/timeframe selects
    group_keys = ['symbol', 'timeframe'] if not is_mt4 else None

    if group_keys:
        grouped = df.groupby(group_keys)
    else:
        grouped = [(None, df)]

    for _, group in grouped:
        # Sort by the appropriate time columns for the format
        group = group.sort_values(sort_cols)
        
        # A. Calculate True Range (TR) and Directional Movement (DM)
        prev_close = group['close'].shift(1)
        prev_high = group['high'].shift(1)
        prev_low = group['low'].shift(1)
        
        tr1 = group['high'] - group['low']
        tr2 = (group['high'] - prev_close).abs()
        tr3 = (group['low'] - prev_close).abs()
        group['tr'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        group['plus_dm'] = np.where((group['high'] - prev_high) > (prev_low - group['low']), 
                                    np.maximum(group['high'] - prev_high, 0), 0)
        group['minus_dm'] = np.where((prev_low - group['low']) > (group['high'] - prev_high), 
                                     np.maximum(prev_low - group['low'], 0), 0)
        
        # B. Smooth TR and DM using Wilder's Smoothing
        atr_smooth = group['tr'].ewm(alpha=1/period, min_periods=period).mean()
        plus_di_smooth = group['plus_dm'].ewm(alpha=1/period, min_periods=period).mean()
        minus_di_smooth = group['minus_dm'].ewm(alpha=1/period, min_periods=period).mean()
        
        # C. Calculate +DI and -DI
        group['plus_di'] = 100 * (plus_di_smooth / atr_smooth)
        group['minus_di'] = 100 * (minus_di_smooth / atr_smooth)
        
        # D. Calculate DX and then ADX
        # Note: Added protection against division by zero
        di_sum = group['plus_di'] + group['minus_di']
        dx = 100 * (group['plus_di'] - group['minus_di']).abs() / di_sum.replace(0, np.nan)
        group['adx'] = dx.ewm(alpha=1/period, min_periods=period).mean()
        
        # E. Filter and Collect
        all_results.append(group[output_cols].dropna(subset=['adx']))

    if not all_results:
        return [output_cols, []]

    # 5. Final Formatting
    final_df = pd.concat(all_results)
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by=sort_cols, ascending=is_asc)
    
    return [output_cols, final_df.values.tolist()]