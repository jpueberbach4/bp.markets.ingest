import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates Point & Figure (P&F) chart data.
    X = Upward price movement (Demand)
    O = Downward price movement (Supply)
    """

    # 1. Parse Parameters
    try:
        box_size = float(options.get('box_size', 10.0))
        reversal = int(options.get('reversal', 3)) # Standard 3-box reversal
    except (ValueError, TypeError):
        box_size, reversal = 10.0, 3

    if not data:
        return [[], []]

    # 2. Determine Price Precision
    try:
        sample_price = str(data[0].get('close', '0.00000'))
        precision = len(sample_price.split('.')[1]) if '.' in sample_price else 2
    except (IndexError, AttributeError):
        precision = 2

    df = pd.DataFrame(data)
    # P&F usually uses High/Low or Close; we will use Close for consistency
    prices = df['close'].astype(float).values
    
    output_cols = ['column', 'type', 'price', 'time']
    results = []
    
    if len(prices) == 0:
        return [output_cols, []]

    # 3. Initialization
    current_col = 0
    # Round initial price to nearest box
    last_h = np.floor(prices[0] / box_size) * box_size
    last_l = last_h
    is_up = True # Start assuming upward trend or neutral
    
    # Use the first timestamp available
    start_time = data[0].get('time', 'N/A')

    # 4. P&F Logic
    for i in range(1, len(prices)):
        price = prices[i]
        time = data[i].get('time', start_time)

        if is_up:
            # Continue Up
            if price >= last_h + box_size:
                num_boxes = int((price - last_h) // box_size)
                for _ in range(num_boxes):
                    last_h += box_size
                    results.append([current_col, 'X', round(last_h, precision), time])
            # Reversal Down
            elif price <= last_h - (box_size * reversal):
                current_col += 1
                num_boxes = int((last_h - price) // box_size)
                last_l = last_h - box_size
                for _ in range(num_boxes):
                    results.append([current_col, 'O', round(last_l, precision), time])
                    last_l -= box_size
                last_l += box_size # Adjust to last drawn O
                is_up = False
        else:
            # Continue Down
            if price <= last_l - box_size:
                num_boxes = int((last_l - price) // box_size)
                for _ in range(num_boxes):
                    last_l -= box_size
                    results.append([current_col, 'O', round(last_l, precision), time])
            # Reversal Up
            elif price >= last_l + (box_size * reversal):
                current_col += 1
                num_boxes = int((price - last_l) // box_size)
                last_h = last_l + box_size
                for _ in range(num_boxes):
                    results.append([current_col, 'X', round(last_h, precision), time])
                    last_h += box_size
                last_h -= box_size # Adjust to last drawn X
                is_up = True

    return [output_cols, results]