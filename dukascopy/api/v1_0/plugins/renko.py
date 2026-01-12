import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates Renko Bricks.
    Renko charts filter out noise by only plotting price changes of a fixed size.
    Output includes: open, high, low, close (of the brick), and direction.
    """

    # 1. Parse Parameters
    try:
        # Brick size can be fixed (e.g., 10.0) or ATR-based in advanced versions
        brick_size = float(options.get('brick_size', 10.0))
    except (ValueError, TypeError):
        brick_size = 10.0

    if not data:
        return [[], []]

    # 2. Determine Price Precision
    try:
        sample_price = str(data[0].get('close', '0.00000'))
        precision = len(sample_price.split('.')[1]) if '.' in sample_price else 2
    except (IndexError, AttributeError):
        precision = 5

    # 3. Prepare DataFrame
    df = pd.DataFrame(data)
    is_mt4 = options.get('mt4') is True
    
    # 4. Dynamic Column Mapping
    # Note: Renko creates new 'bars', so we track the original time it was formed
    if is_mt4:
        output_cols = ['date', 'time', 'open', 'high', 'low', 'close', 'direction']
        sort_cols = ['date', 'time']
    else:
        output_cols = ['symbol', 'timeframe', 'time', 'open', 'high', 'low', 'close', 'direction']
        sort_cols = ['time']

    for col in ['close']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    all_results = []
    group_keys = ['symbol', 'timeframe'] if not is_mt4 else None
    grouped = df.groupby(group_keys) if group_keys else [(None, df)]

    for _, group in grouped:
        group = group.sort_values(sort_cols).reset_index(drop=True)
        
        bricks = []
        if group.empty:
            continue

        # Initialize first brick
        first_close = group.loc[0, 'close']
        # Round to nearest brick level
        prev_close = np.round(first_close / brick_size) * brick_size
        prev_open = prev_close - brick_size
        
        for i, row in group.iterrows():
            price = row['close']
            
            # Upward Movement
            while price >= prev_close + brick_size:
                new_open = prev_close
                new_close = prev_close + brick_size
                
                brick = row.to_dict()
                brick.update({
                    'open': new_open,
                    'high': new_close,
                    'low': new_open,
                    'close': new_close,
                    'direction': 1
                })
                bricks.append(brick)
                prev_open, prev_close = new_open, new_close

            # Downward Movement
            while price <= prev_close - brick_size:
                new_open = prev_close
                new_close = prev_close - brick_size
                
                brick = row.to_dict()
                brick.update({
                    'open': new_open,
                    'high': new_open,
                    'low': new_close,
                    'close': new_close,
                    'direction': -1
                })
                bricks.append(brick)
                prev_open, prev_close = new_open, new_close

        if bricks:
            renko_df = pd.DataFrame(bricks)
            # 5. Apply Dynamic Rounding
            for col in ['open', 'high', 'low', 'close']:
                renko_df[col] = renko_df[col].round(precision)
            
            all_results.append(renko_df[output_cols])

    if not all_results:
        return [output_cols, []]

    # 6. Final Formatting
    final_df = pd.concat(all_results)
    is_asc = options.get('order', 'asc').lower() == 'asc'
    final_df = final_df.sort_values(by=sort_cols, ascending=is_asc)
    
    # Final safety gate for JSON compliance
    data_as_list = final_df.values.tolist()
    clean_data = [
        [(x if (isinstance(x, (float, np.floating)) and np.isfinite(x)) else x) for x in row]
        for row in data_as_list
    ]
    
    return [output_cols, clean_data]