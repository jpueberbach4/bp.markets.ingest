import pandas as pd
import numpy as np
from typing import List, Dict, Any

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: kagi_0.05_percent -> {'reversal': '0.05', 'mode': 'percent'}
    """
    return {
        "reversal": args[0] if len(args) > 0 else "10.0",
        "mode": args[1] if len(args) > 1 else "fixed"
    }

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    High-performance Kagi Chart calculation.
    Yang = Thick line (Bullish, price > previous shoulder)
    Yin = Thin line (Bearish, price < previous waist)
    """
    # 1. Parse Parameters
    try:
        reversal = float(options.get('reversal', 10.0))
        is_percentage = options.get('mode', 'fixed') == 'percent'
    except (ValueError, TypeError):
        reversal, is_percentage = 10.0, False

    # 2. Determine Price Precision
    try:
        sample_price = str(df['close'].iloc[0])
        precision = len(sample_price.split('.')[1]) if '.' in sample_price else 2
    except (IndexError, AttributeError):
        precision = 2

    # 3. Path-Dependent Calculation (NumPy Accelerated)
    prices = df['close'].values
    times = df.index.values # Assuming index is time-based from parallel.py
    
    # Kagi requires a loop because each state depends on the previous reversal
    kagi_prices = []
    kagi_times = []
    kagi_thickness = [] # 1 for Yang (Thick), 0 for Yin (Thin)
    kagi_direction = [] # 1 for Up, -1 for Down
    
    if len(prices) < 1:
        return pd.DataFrame()

    # Initialization
    current_price = prices[0]
    direction = 0 # 1: Up, -1: Down
    thickness = 1 # Start as Yang
    prev_shoulder = current_price
    prev_waist = current_price
    
    kagi_prices.append(current_price)
    kagi_times.append(times[0])
    kagi_thickness.append(thickness)
    kagi_direction.append(0)

    for i in range(1, len(prices)):
        price = prices[i]
        rev_amt = (current_price * (reversal / 100)) if is_percentage else reversal
        
        if direction == 0:
            if abs(price - current_price) >= rev_amt:
                direction = 1 if price > current_price else -1
                current_price = price
        
        elif direction == 1: # Moving Up
            if price >= current_price:
                current_price = price
                if current_price > prev_shoulder: thickness = 1 # Turn Yang
            elif price <= current_price - rev_amt:
                # Reversal Down
                prev_shoulder = current_price
                direction = -1
                current_price = price
                kagi_prices.append(current_price)
                kagi_times.append(times[i])
                kagi_direction.append(direction)
                kagi_thickness.append(thickness)
                if current_price < prev_waist: thickness = 0 # Turn Yin
                
        elif direction == -1: # Moving Down
            if price <= current_price:
                current_price = price
                if current_price < prev_waist: thickness = 0 # Turn Yin
            elif price >= current_price + rev_amt:
                # Reversal Up
                prev_waist = current_price
                direction = 1
                current_price = price
                kagi_prices.append(current_price)
                kagi_times.append(times[i])
                kagi_direction.append(direction)
                kagi_thickness.append(thickness)
                if current_price > prev_shoulder: thickness = 1 # Turn Yang

    # 4. Final Formatting
    res = pd.DataFrame({
        'price': kagi_prices,
        'direction': kagi_direction,
        'thickness': kagi_thickness
    }, index=kagi_times)
    
    return res.round(precision)