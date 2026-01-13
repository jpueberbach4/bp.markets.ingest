import pandas as pd
import numpy as np
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "The Parabolic SAR (Stop and Reverse) is a trend-following indicator used to "
        "identify potential reversals in price movement. It appears as a series of "
        "dots placed either above or below the price: dots below indicate a bullish "
        "trend, while dots above indicate a bearish trend. The indicator 'accelerates' "
        "as the trend continues, moving closer to the price to provide dynamic trailing "
        "stop-loss levels."
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
    PSAR is a recursive state machine. 
    A warmup is required to establish the correct trend direction (Bull/Bear),
    the Extreme Point (EP), and the Acceleration Factor (AF).
    """
    # 100 bars is the industry standard to ensure the Parabolic SAR 
    # has locked onto the trend and the acceleration has stabilized.
    return 100

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: psar_0.02_0.2 -> {'step': '0.02', 'max_step': '0.2'}
    """
    return {
        "step": args[0] if len(args) > 0 else "0.02",
        "max_step": args[1] if len(args) > 1 else "0.2"
    }

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    High-performance Parabolic SAR (Stop and Reverse) calculation.
    Uses a NumPy state machine for recursive path-dependency.
    """
    # 1. Parse Parameters
    try:
        step = float(options.get('step', 0.02))
        max_step = float(options.get('max_step', 0.2))
    except (ValueError, TypeError):
        step, max_step = 0.02, 0.2

    # 2. Determine Price Precision
    try:
        sample_price = str(df['close'].iloc[0])
        precision = len(sample_price.split('.')[1]) if '.' in sample_price else 2
    except (IndexError, AttributeError):
        precision = 5

    # 3. Path-Dependent Calculation (NumPy Accelerated)
    highs = df['high'].values
    lows = df['low'].values
    n = len(df)
    
    psar = np.zeros(n)
    bull = True # Initial trend direction
    af = step
    ep = highs[0]
    psar[0] = lows[0] # Initial SAR

    # State machine loop
    for i in range(1, n):
        prev_psar = psar[i-1]
        
        if bull:
            psar[i] = prev_psar + af * (ep - prev_psar)
            # SAR cannot be higher than the lows of the previous two periods
            psar[i] = min(psar[i], lows[i-1], lows[max(0, i-2)])
            
            # Check for reversal
            if lows[i] < psar[i]:
                bull = False
                psar[i] = ep # SAR reverses to the previous Extreme Point
                ep = lows[i]
                af = step
            else:
                if highs[i] > ep:
                    ep = highs[i]
                    af = min(af + step, max_step)
        else:
            psar[i] = prev_psar + af * (ep - prev_psar)
            # SAR cannot be lower than the highs of the previous two periods
            psar[i] = max(psar[i], highs[i-1], highs[max(0, i-2)])
            
            # Check for reversal
            if highs[i] > psar[i]:
                bull = True
                psar[i] = ep
                ep = highs[i]
                af = step
            else:
                if lows[i] < ep:
                    ep = lows[i]
                    af = min(af + step, max_step)

    # 4. Final Formatting and Rounding
    # Preserving the original index for O(1) merging in parallel.py
    res = pd.DataFrame({
        'psar': psar
    }, index=df.index)
    
    return res.round(precision)