import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates Hull Moving Average (HMA).
    Formula: WMA(2*WMA(n/2) - WMA(n), sqrt(n))
    """

    # 1. Parse Parameters
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14

    if not data:
        return [[], []]

    # 2. Prepare DataFrame
    df = pd.DataFrame(data)
    is_mt4 = options.get('mt4') is True
    
    if is_mt4:
        output_cols = ['date', 'time', 'hma']
        sort_cols = ['date', 'time']
    else:
        output_cols = ['symbol', 'timeframe', 'time', 'hma']
        sort_cols = ['time']

    df['close'] = pd.to_numeric(df['close'], errors='coerce')
    
    all_results = []
    group_keys = ['symbol', 'timeframe'] if not is_mt4 else None
    grouped = df.groupby(group_keys) if group_keys else [(None, df)]

    for _, group in grouped:
        group = group.sort_values(sort_cols)
        
        # Helper for Weighted Moving Average
        def wma(series, n):
            weights = np.arange(1, n + 1)
            return series.rolling(n).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True)

        # A. Calculation Logic
        half_period = int(period / 2)
        sqrt_period = int(np.sqrt(period))

        # 2 * WMA(n/2) - WMA(n)
        raw_hma = (2 * wma(group['close'], half_period)) - wma(group['close'], period)
        
        # Final smoothing: WMA(raw_hma, sqrt(n))
        group['hma'] = wma(raw_hma, sqrt_period)
        
        # Drop warm-up rows (roughly period + sqrt_period)
        all_results.append(group[output_cols].dropna(subset=['hma']))

    if not all_results:
        return [output_cols, []]

    final_df = pd.concat(all_results)
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by=sort_cols, ascending=is_asc)
    
    # JSON compliance cleanup
    final_df = final_df.replace([np.inf, -np.inf], np.nan)
    result_list = final_df.where(pd.notnull(final_df), None).values.tolist()
    
    return [output_cols, result_list]