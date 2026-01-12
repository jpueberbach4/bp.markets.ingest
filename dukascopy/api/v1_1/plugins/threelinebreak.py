import pandas as pd
import numpy as np
from typing import List, Dict, Any

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: tlb_3 -> {'break': '3'}
    """
    return {
        "break": args[0] if len(args) > 0 else "3"
    }

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    High-performance Three Line Break (TLB) calculation.
    A reversal only occurs if price breaks the high/low of the last 'n' lines.
    """
    # 1. Parse Parameters
    try:
        break_count = int(options.get('break', 3))
    except (ValueError, TypeError):
        break_count = 3

    # 2. Determine Price Precision
    try:
        sample_price = str(df['close'].iloc[0])
        precision = len(sample_price.split('.')[1]) if '.' in sample_price else 2
    except (IndexError, AttributeError):
        precision = 2

    # 3. Path-Dependent Calculation (NumPy Accelerated)
    prices = df['close'].values
    times = df.index.values
    
    tlb_open = []
    tlb_close = []
    tlb_times = []
    tlb_types = [] # 'up', 'down', 'reversal_up', 'reversal_down'

    if len(prices) < 1:
        return pd.DataFrame()

    # Initialization with the first price
    # We use a list of lines to track the 'break_count' history
    # Each line is stored as [open, close]
    lines = [[prices[0], prices[0]]]
    
    for i in range(1, len(prices)):
        price = prices[i]
        last_line = lines[-1]
        last_open = last_line[0]
        last_close = last_line[1]
        is_up = last_close > last_open

        # Scenario A: Trend Continuation
        if is_up and price > last_close:
            new_line = [last_close, price]
            lines.append(new_line)
            tlb_open.append(new_line[0])
            tlb_close.append(new_line[1])
            tlb_times.append(times[i])
            tlb_types.append('up')
        elif not is_up and price < last_close:
            new_line = [last_close, price]
            lines.append(new_line)
            tlb_open.append(new_line[0])
            tlb_close.append(new_line[1])
            tlb_times.append(times[i])
            tlb_types.append('down')
            
        # Scenario B: Reversal Check
        else:
            # Look at the extremes of the last 'n' lines
            recent = lines[-break_count:]
            # Determine high/low of those lines
            flat_recent = [val for sublist in recent for val in sublist]
            extreme_high = max(flat_recent)
            extreme_low = min(flat_recent)
            
            if is_up and price < extreme_low:
                new_line = [last_close, price]
                lines.append(new_line)
                tlb_open.append(new_line[0])
                tlb_close.append(new_line[1])
                tlb_times.append(times[i])
                tlb_types.append('reversal_down')
            elif not is_up and price > extreme_high:
                new_line = [last_close, price]
                lines.append(new_line)
                tlb_open.append(new_line[0])
                tlb_close.append(new_line[1])
                tlb_times.append(times[i])
                tlb_types.append('reversal_up')

    # 4. Final Formatting
    res = pd.DataFrame({
        'open': tlb_open,
        'close': tlb_close,
        'type': tlb_types
    }, index=tlb_times)
    
    return res.round(precision)