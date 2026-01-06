import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates Average Directional Index (ADX), +DI, and -DI.
    Standard: 14 periods with Wilder's Smoothing.
    """

    # Parse Period
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14

    options['period'] = str(period)

    if not data:
        return [[], []]

    # Prepare DataFrame
    df = pd.DataFrame(data)
    df['close'] = pd.to_numeric(df['close'])
    df['high'] = pd.to_numeric(df['high'])
    df['low'] = pd.to_numeric(df['low'])
    
    output_cols = ['symbol', 'timeframe', 'time', 'adx', 'plus_di', 'minus_di']
    all_results = []

    grouped = df.groupby(['symbol', 'timeframe'])

    for (symbol, timeframe), group in grouped:
        group = group.sort_values('time')
        
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
        # Wilder's Smoothing is equivalent to ewm(alpha=1/period)
        atr_smooth = group['tr'].ewm(alpha=1/period, min_periods=period).mean()
        plus_di_smooth = group['plus_dm'].ewm(alpha=1/period, min_periods=period).mean()
        minus_di_smooth = group['minus_dm'].ewm(alpha=1/period, min_periods=period).mean()
        
        # C. Calculate +DI and -DI
        group['plus_di'] = 100 * (plus_di_smooth / atr_smooth)
        group['minus_di'] = 100 * (minus_di_smooth / atr_smooth)
        
        # D. Calculate DX and then ADX
        dx = 100 * (group['plus_di'] - group['minus_di']).abs() / (group['plus_di'] + group['minus_di'])
        group['adx'] = dx.ewm(alpha=1/period, min_periods=period).mean()
        
        all_results.append(group[output_cols].dropna(subset=['adx']))

    if not all_results:
        return [output_cols, []]

    # Final Formatting
    final_df = pd.concat(all_results)
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by='time', ascending=is_asc)
    
    return [output_cols, final_df.values.tolist()]