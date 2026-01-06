import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates Average True Range (ATR) per Symbol/Timeframe.
    Standard: Wilder's Smoothing over 14 periods.
    """

    # Parse Period
    raw_period = options.get('period', 14)
    try:
        period = int(raw_period)
    except (ValueError, TypeError):
        period = 14

    options['period'] = str(period)

    if not data:
        return [[], []]

    # Prepare DataFrame - ATR needs High, Low, and Close
    df = pd.DataFrame(data)
    df['close'] = pd.to_numeric(df['close'])
    df['high'] = pd.to_numeric(df['high'])
    df['low'] = pd.to_numeric(df['low'])
    
    output_cols = ['symbol', 'timeframe', 'time', 'atr']
    all_results = []

    # Group and Calculate
    grouped = df.groupby(['symbol', 'timeframe'])

    for (symbol, timeframe), group in grouped:
        group = group.sort_values('time')
        
        # A. Calculate True Range (TR)
        # TR is the greatest of:
        # 1. Current High - Current Low
        # 2. Abs(Current High - Previous Close)
        # 3. Abs(Current Low - Previous Close)
        
        prev_close = group['close'].shift(1)
        
        tr1 = group['high'] - group['low']
        tr2 = (group['high'] - prev_close).abs()
        tr3 = (group['low'] - prev_close).abs()
        
        group['tr'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # Calculate ATR using Wilder's Smoothing (EMA with alpha = 1/period)
        # Note: com = period - 1 is equivalent to Wilder's Smoothing
        group['atr'] = group['tr'].ewm(com=period - 1, min_periods=period).mean()
        
        # Remove the warm-up period
        all_results.append(group[output_cols].dropna(subset=['atr']))

    if not all_results:
        return [output_cols, []]

    # Final Formatting
    final_df = pd.concat(all_results)
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by='time', ascending=is_asc)
    
    return [output_cols, final_df.values.tolist()]