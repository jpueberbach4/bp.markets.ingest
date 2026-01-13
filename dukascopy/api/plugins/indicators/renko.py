import pandas as pd
import numpy as np
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "Renko charts are time-independent charts that filter out minor price "
        "fluctuations by focusing solely on price movement. They are constructed "
        "using 'bricks' of a fixed size; a new brick is only added when price "
        "moves a full brick size away from the previous one. This creates a "
        "cleaner visualization of trends and support/resistance levels, as the "
        "element of time is removed from the horizontal axis."
    )

def meta()->Dict:
    """
    Any other metadata to pass via API
    """
    return {
        "author": "Google Gemini",
        "version": 1.0
    }
    
def warmup_count(options: Dict[str, Any]) -> int:
    """
    Renko charts are path-dependent and ignore time.
    A warmup is required to establish the 'last brick' price 
    so that the first visible brick is accurately placed.
    """
    # 250 bars is standard for Renko to ensure the brick 
    # levels have stabilized relative to the price trend.
    return 250

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: renko_10 -> {'brick_size': '10'}
    """
    return {
        "brick_size": args[0] if len(args) > 0 else "10.0"
    }

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    High-performance Renko Brick calculation.
    Filters price noise by only recording moves of a fixed brick size.
    """
    # 1. Parse Parameters
    try:
        brick_size = float(options.get('brick_size', 10.0))
    except (ValueError, TypeError):
        brick_size = 10.0

    # 2. Determine Price Precision
    try:
        sample_price = str(df['close'].iloc[0])
        precision = len(sample_price.split('.')[1]) if '.' in sample_price else 2
    except (IndexError, AttributeError):
        precision = 2

    # 3. Path-Dependent Calculation (NumPy Accelerated)
    prices = df['close'].values
    times = df.index.values
    
    renko_open = []
    renko_close = []
    renko_times = []
    renko_dir = [] # 1 for Up, -1 for Down

    if len(prices) < 1:
        return pd.DataFrame()

    # Initialization
    # First brick is formed from the first price rounded to the brick size
    prev_close = np.floor(prices[0] / brick_size) * brick_size
    prev_open = prev_close - brick_size 

    for i in range(1, len(prices)):
        price = prices[i]
        
        # Calculate price change relative to the last brick
        # Upward move
        if price >= prev_close + brick_size:
            num_bricks = int((price - prev_close) // brick_size)
            for _ in range(num_bricks):
                new_open = prev_close
                new_close = prev_close + brick_size
                
                renko_open.append(new_open)
                renko_close.append(new_close)
                renko_times.append(times[i])
                renko_dir.append(1)
                
                prev_open, prev_close = new_open, new_close
                
        # Downward move
        elif price <= prev_close - brick_size:
            num_bricks = int((prev_close - price) // brick_size)
            for _ in range(num_bricks):
                new_open = prev_close
                new_close = prev_close - brick_size
                
                renko_open.append(new_open)
                renko_close.append(new_close)
                renko_times.append(times[i])
                renko_dir.append(-1)
                
                prev_open, prev_close = new_open, new_close

    # 4. Final Formatting
    res = pd.DataFrame({
        'open': renko_open,
        'high': np.maximum(renko_open, renko_close),
        'low': np.minimum(renko_open, renko_close),
        'close': renko_close,
        'direction': renko_dir
    }, index=renko_times)
    
    return res.round(precision)