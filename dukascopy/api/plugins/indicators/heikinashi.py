import pandas as pd
import numpy as np
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "Heikin Ashi is a modified candlestick charting method that filters market "
        "noise to provide a clearer view of trend direction and strength. Unlike "
        "standard candles, each Heikin Ashi candle is calculated using a recursive "
        "formula that averages the current and previous price data, resulting in "
        "smoother price action where green candles represent strong uptrends and "
        "red candles represent strong downtrends."
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
    Heikin Ashi is recursive. While it doesn't have a fixed window,
    a warmup period ensures the HA_Open prices have converged and 
    properly reflect the prior trend.
    """
    # 50 rows is a standard buffer to stabilize recursive candle calculations
    return 50

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Heikin Ashi typically takes no parameters.
    """
    return {}

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    High-performance Heikin Ashi calculation.
    Formula:
    - HA_Close = (Open + High + Low + Close) / 4
    - HA_Open = (Prev_HA_Open + Prev_HA_Close) / 2
    - HA_High = Max(High, HA_Open, HA_Close)
    - HA_Low = Min(Low, HA_Open, HA_Close)
    """
    
    # 1. Determine Price Precision for rounding
    try:
        sample_price = str(df['close'].iloc[0])
        precision = len(sample_price.split('.')[1]) if '.' in sample_price else 2
    except (IndexError, AttributeError):
        precision = 5

    # 2. Vectorized HA Close
    ha_close = (df['open'] + df['high'] + df['low'] + df['close']) / 4
    
    # 3. Optimized HA Open (Recursive logic requires a loop, but we use NumPy for speed)
    # Converting to numpy array for much faster iteration than Pandas .iloc
    ha_open = np.zeros(len(df))
    opens = df['open'].values
    closes = df['close'].values
    ha_close_values = ha_close.values
    
    # Seed the first HA Open
    ha_open[0] = (opens[0] + closes[0]) / 2
    
    # Sequential calculation of HA Open
    for i in range(1, len(df)):
        ha_open[i] = (ha_open[i-1] + ha_close_values[i-1]) / 2
        
    # 4. Vectorized HA High and HA Low
    # Max/Min across the original high/low and the new HA open/close
    ha_high = np.maximum(df['high'].values, np.maximum(ha_open, ha_close_values))
    ha_low = np.minimum(df['low'].values, np.minimum(ha_open, ha_close_values))

    # 5. Final Formatting and Rounding
    # Preserving the original index for O(1) merging in parallel.py
    res = pd.DataFrame({
        'ha_open': ha_open,
        'ha_high': ha_high,
        'ha_low': ha_low,
        'ha_close': ha_close_values
    }, index=df.index).round(precision)
    
    return res