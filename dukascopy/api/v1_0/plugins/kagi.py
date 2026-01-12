import pandas as pd
import numpy as np

def calculate(data, options):
    """
    Calculates Kagi Chart data.
    Yang = Thick line (Bullish, price > previous shoulder)
    Yin = Thin line (Bearish, price < previous waist)
    """

    # 1. Parse Parameters
    try:
        # Reversal can be fixed value or percentage
        reversal = float(options.get('reversal', 10.0))
        is_percentage = options.get('mode', 'fixed') == 'percent'
    except (ValueError, TypeError):
        reversal, is_percentage = 10.0, False

    if not data:
        return [[], []]

    # 2. Determine Price Precision
    try:
        sample_price = str(data[0].get('close', '0.00000'))
        precision = len(sample_price.split('.')[1]) if '.' in sample_price else 2
    except (IndexError, AttributeError):
        precision = 2

    prices = [float(d['close']) for d in data]
    times = [d['time'] for d in data]
    
    output_cols = ['time', 'price', 'direction', 'thickness', 'type']
    results = []

    # 3. Initialization
    current_price = prices[0]
    direction = 0 # 1 for Up, -1 for Down
    thickness = 1 # 1 for Yang (Thick), 0 for Yin (Thin)
    
    # Track key levels for thickness switching
    prev_shoulder = float('-inf')
    prev_waist = float('inf')
    
    results.append([times[0], round(current_price, precision), 0, thickness, 'start'])

    # 4. Kagi Logic
    for i in range(1, len(prices)):
        price = prices[i]
        time = times[i]
        
        # Calculate dynamic reversal amount if in percentage mode
        rev_amt = (current_price * (reversal / 100)) if is_percentage else reversal

        if direction == 0:
            if price >= current_price + rev_amt:
                direction = 1
                current_price = price
            elif price <= current_price - rev_amt:
                direction = -1
                current_price = price
        
        elif direction == 1: # Moving Up
            if price >= current_price:
                current_price = price
                # Switch to Yang if we break previous shoulder
                if current_price > prev_shoulder:
                    thickness = 1
            elif price <= current_price - rev_amt:
                # Reversal Down (Shoulder formed)
                prev_shoulder = current_price
                direction = -1
                current_price = price
                results.append([time, round(prev_shoulder, precision), -1, thickness, 'shoulder'])
                # Check if new price immediately makes it Yin
                if current_price < prev_waist:
                    thickness = 0

        elif direction == -1: # Moving Down
            if price <= current_price:
                current_price = price
                # Switch to Yin if we break previous waist
                if current_price < prev_waist:
                    thickness = 0
            elif price >= current_price + rev_amt:
                # Reversal Up (Waist formed)
                prev_waist = current_price
                direction = 1
                current_price = price
                results.append([time, round(prev_waist, precision), 1, thickness, 'waist'])
                # Check if new price immediately makes it Yang
                if current_price > prev_shoulder:
                    thickness = 1

    return [output_cols, results]