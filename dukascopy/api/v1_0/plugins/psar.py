import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates Parabolic SAR (Stop and Reverse).
    Defaults: Step (0.02), Max Step (0.2).
    """

    # 1. Parse Parameters
    try:
        step = float(options.get('step', 0.02))
        max_step = float(options.get('max_step', 0.2))
    except (ValueError, TypeError):
        step, max_step = 0.02, 0.2

    if not data:
        return [[], []]

    # 2. Prepare DataFrame
    df = pd.DataFrame(data)
    is_mt4 = options.get('mt4') is True
    
    if is_mt4:
        output_cols = ['date', 'time', 'psar']
        sort_cols = ['date', 'time']
    else:
        output_cols = ['symbol', 'timeframe', 'time', 'psar']
        sort_cols = ['time']

    for col in ['high', 'low']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    all_results = []
    group_keys = ['symbol', 'timeframe'] if not is_mt4 else None
    grouped = df.groupby(group_keys) if group_keys else [(None, df)]

    for _, group in grouped:
        group = group.sort_values(sort_cols).reset_index(drop=True)
        
        # Initialize columns
        highs = group['high'].values
        lows = group['low'].values
        psar = np.zeros(len(group))
        
        # Initial state (assuming starting with a long position)
        bull = True
        af = step
        ep = highs[0]
        psar[0] = lows[0]

        # 3. Recursive Calculation Loop
        for i in range(1, len(group)):
            prev_psar = psar[i-1]
            
            if bull:
                psar[i] = prev_psar + af * (ep - prev_psar)
                # Ensure SAR doesn't enter the range of previous two lows
                psar[i] = min(psar[i], lows[i-1], lows[max(0, i-2)])
                
                # Check for reversal
                if lows[i] < psar[i]:
                    bull = False
                    psar[i] = ep # Reverse to Extreme Point
                    ep = lows[i]
                    af = step
                else:
                    if highs[i] > ep:
                        ep = highs[i]
                        af = min(af + step, max_step)
            else:
                psar[i] = prev_psar + af * (ep - prev_psar)
                # Ensure SAR doesn't enter the range of previous two highs
                psar[i] = max(psar[i], highs[i-1], highs[max(0, i-2)])
                
                # Check for reversal
                if highs[i] > psar[i]:
                    bull = True
                    psar[i] = ep # Reverse to Extreme Point
                    ep = highs[i]
                    af = step
                else:
                    if lows[i] < ep:
                        ep = lows[i]
                        af = min(af + step, max_step)

        group['psar'] = psar
        all_results.append(group[output_cols])

    if not all_results:
        return [output_cols, []]

    final_df = pd.concat(all_results)
    
    # Handle Sort
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by=sort_cols, ascending=is_asc)
    
    # 4. JSON Compliance Guard
    final_df = final_df.replace([np.inf, -np.inf], np.nan)
    result_list = final_df.where(pd.notnull(final_df), None).values.tolist()
    
    return [output_cols, result_list]