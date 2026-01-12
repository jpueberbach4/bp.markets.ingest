import pandas as pd
import numpy as np
from typing import List, Dict, Any

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: pf_10_3 -> {'box_size': '10', 'reversal': '3'}
    """
    return {
        "box_size": args[0] if len(args) > 0 else "10.0",
        "reversal": args[1] if len(args) > 1 else "3"
    }

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    High-performance Point & Figure (P&F) calculation.
    X = Up (Demand), O = Down (Supply).
    """
    # 1. Parse Parameters
    try:
        box_size = float(options.get('box_size', 10.0))
        reversal = int(options.get('reversal', 3))
    except (ValueError, TypeError):
        box_size, reversal = 10.0, 3

    # 2. Determine Price Precision
    try:
        sample_price = str(df['close'].iloc[0])
        precision = len(sample_price.split('.')[1]) if '.' in sample_price else 2
    except (IndexError, AttributeError):
        precision = 2

    # 3. Path-Dependent Calculation (NumPy Accelerated)
    prices = df['close'].values
    times = df.index.values # Assuming index is time-based from parallel.py
    
    pf_times = []
    pf_types = [] # 1 for X, -1 for O
    pf_prices = []
    pf_columns = []

    if len(prices) < 1:
        return pd.DataFrame()

    # Initialization
    last_price = prices[0]
    # Round to nearest box floor
    last_h = last_l = np.floor(last_price / box_size) * box_size
    current_col = 0
    is_up = True # Start assuming upward trend
    
    for i in range(1, len(prices)):
        price = prices[i]
        
        if is_up:
            # Continue up?
            if price >= last_h + box_size:
                num_boxes = int((price - last_h) // box_size)
                for _ in range(num_boxes):
                    last_h += box_size
                    pf_times.append(times[i])
                    pf_prices.append(last_h)
                    pf_types.append("X")
                    pf_columns.append(current_col)
            # Reversal down?
            elif price <= last_h - (box_size * reversal):
                is_up = False
                current_col += 1
                num_boxes = int((last_h - price) // box_size)
                last_l = last_h - box_size
                for _ in range(num_boxes):
                    pf_times.append(times[i])
                    pf_prices.append(last_l)
                    pf_types.append("O")
                    pf_columns.append(current_col)
                    last_l -= box_size
                last_l += box_size # Reset to the last plotted O
        else:
            # Continue down?
            if price <= last_l - box_size:
                num_boxes = int((last_l - price) // box_size)
                for _ in range(num_boxes):
                    last_l -= box_size
                    pf_times.append(times[i])
                    pf_prices.append(last_l)
                    pf_types.append("O")
                    pf_columns.append(current_col)
            # Reversal up?
            elif price >= last_l + (box_size * reversal):
                is_up = True
                current_col += 1
                num_boxes = int((price - last_l) // box_size)
                last_h = last_l + box_size
                for _ in range(num_boxes):
                    pf_times.append(times[i])
                    pf_prices.append(last_h)
                    pf_types.append("X")
                    pf_columns.append(current_col)
                    last_h += box_size
                last_h -= box_size # Reset to the last plotted X

    # 4. Final Formatting
    res = pd.DataFrame({
        'column': pf_columns,
        'type': pf_types,
        'price': pf_prices
    }, index=pf_times)
    
    return res.round(precision)