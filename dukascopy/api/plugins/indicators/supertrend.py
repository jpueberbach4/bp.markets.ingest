import pandas as pd
import numpy as np
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "Supertrend is a trend-following indicator that provides clear buy and sell "
        "signals. It is calculated using the Average True Range (ATR) and a "
        "multiplier to create upper and lower bands. When price closes above the "
        "upper band, the indicator turns green (bullish), and when it closes below "
        "the lower band, it turns red (bearish). It is highly effective as a "
        "trailing stop-loss and for identifying the current market regime."
    )

def meta()->Dict:
    """
    Any other metadata to pass via API
    """
    return {
        "author": "Google Gemini",
        "version": 1.0,
        "verified": 0,
        "needs": "debug"
    }
    
def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for Supertrend.
    Supertrend uses ATR (Wilder's Smoothing) and a recursive state 
    machine for the final bands. We use 3x period for stabilization.
    """
    try:
        period = int(options.get('period', 10))
    except (ValueError, TypeError):
        period = 10

    # 3x period ensures the ATR has converged and the 
    # trend direction logic has stabilized.
    return period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: supertrend_10_3 -> {'period': '10', 'multiplier': '3'}
    """
    return {
        "period": args[0] if len(args) > 0 else "10",
        "multiplier": args[1] if len(args) > 1 else "3.0"
    }

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    High-performance Supertrend calculation.
    Uses ATR and price extremes to determine trend direction and trailing stops.
    """
    # 1. Parse Parameters
    try:
        period = int(options.get('period', 10))
        multiplier = float(options.get('multiplier', 3.0))
    except (ValueError, TypeError):
        period, multiplier = 10, 3.0

    # 2. Determine Price Precision
    try:
        sample_price = str(df['close'].iloc[0])
        precision = len(sample_price.split('.')[1]) if '.' in sample_price else 2
    except (IndexError, AttributeError):
        precision = 5

    # 3. Vectorized Pre-calculations
    high = df['high'].values
    low = df['low'].values
    close = df['close'].values
    
    # ATR Calculation (Vectorized)
    tr1 = high - low
    tr2 = np.abs(high - np.roll(close, 1))
    tr3 = np.abs(low - np.roll(close, 1))
    tr = np.maximum.reduce([tr1, tr2, tr3])
    tr[0] = tr1[0] # Fix first element shifted by roll
    
    # Simple Moving Average for ATR
    atr = pd.Series(tr).rolling(window=period).mean().values
    
    # Basic Bands
    hl2 = (high + low) / 2
    basic_ub = hl2 + (multiplier * atr)
    basic_lb = hl2 - (multiplier * atr)

    # 4. Path-Dependent Logic (NumPy Accelerated)
    n = len(df)
    final_ub = np.zeros(n)
    final_lb = np.zeros(n)
    st = np.zeros(n)
    direction = np.ones(n) # 1 for bull, -1 for bear

    for i in range(1, n):
        # Calculate Final Upper Band
        if basic_ub[i] < final_ub[i-1] or close[i-1] > final_ub[i-1]:
            final_ub[i] = basic_ub[i]
        else:
            final_ub[i] = final_ub[i-1]
            
        # Calculate Final Lower Band
        if basic_lb[i] > final_lb[i-1] or close[i-1] < final_lb[i-1]:
            final_lb[i] = basic_lb[i]
        else:
            final_lb[i] = final_lb[i-1]
            
        # Determine Trend Direction and Supertrend value
        if direction[i-1] == 1:
            if close[i] <= final_lb[i]:
                direction[i] = -1
                st[i] = final_ub[i]
            else:
                direction[i] = 1
                st[i] = final_lb[i]
        else:
            if close[i] >= final_ub[i]:
                direction[i] = 1
                st[i] = final_lb[i]
            else:
                direction[i] = -1
                st[i] = final_ub[i]

    # 5. Final Formatting
    # Preserving the original index for O(1) merging in parallel.py
    res = pd.DataFrame({
        'supertrend': st,
        # 'direction': direction
    }, index=df.index)
    
    # Warm-up period cleanup (ATR requires 'period' bars)
    res.iloc[:period, res.columns.get_loc('supertrend')] = np.nan
    
    return res.round(precision).dropna(subset=['supertrend'])