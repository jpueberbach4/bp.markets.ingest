import pandas as pd
import numpy as np
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "The Ichimoku Cloud (Ichimoku Kinko Hyo) is a comprehensive indicator that "
        "defines support and resistance, identifies trend direction, and gauges "
        "momentum. It consists of five lines: the Tenkan-sen (Conversion), Kijun-sen "
        "(Base), Senkou Span A and B (which form the 'Cloud'), and the Chikou Span "
        "(Lagging). A price above the cloud indicates a bullish trend, while price "
        "below suggests a bearish trend."
    )

def meta()->Dict:
    """
    Any other metadata to pass via API
    """
    return {
        "author": "Google Gemini",
        "version": 1.0,
        "verified": 0,
        "needs": "surface-colouring"
    }
    
def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for Ichimoku Cloud.
    Requires the largest window (senkou_p) plus the displacement 
    to ensure the cloud is fully formed at the start date.
    """
    try:
        kijun_p = int(options.get('kijun', 26))
        senkou_p = int(options.get('senkou', 52))
        displace = int(options.get('displacement', kijun_p))
    except (ValueError, TypeError):
        senkou_p, displace = 52, 26

    # Mathematical Requirement:
    # We need senkou_p rows to calculate Span B, 
    # then it is shifted by 'displace' rows.
    # We use a 2x buffer on the total to ensure trend stability.
    return (senkou_p + displace) * 2

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: ichimoku_9_26_52 -> {'tenkan': '9', 'kijun': '26', 'senkou': '52'}
    """
    return {
        "tenkan": args[0] if len(args) > 0 else "9",
        "kijun": args[1] if len(args) > 1 else "26",
        "senkou": args[2] if len(args) > 2 else "52"
    }

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    High-performance vectorized Ichimoku Cloud calculation.
    """
    # 1. Parse Parameters
    try:
        tenkan_p = int(options.get('tenkan', 9))
        kijun_p = int(options.get('kijun', 26))
        senkou_p = int(options.get('senkou', 52))
        # Displacement is typically equal to the Kijun period
        displace = int(options.get('displacement', kijun_p))
    except (ValueError, TypeError):
        tenkan_p, kijun_p, senkou_p, displace = 9, 26, 52, 26

    # 2. Determine Price Precision
    try:
        sample_price = str(df['close'].iloc[0])
        precision = len(sample_price.split('.')[1])+1 if '.' in sample_price else 2
    except (IndexError, AttributeError):
        precision = 5

    # 3. Vectorized Calculations
    # Tenkan-sen (Conversion Line): (9-period high + 9-period low) / 2
    tenkan_h = df['high'].rolling(window=tenkan_p).max()
    tenkan_l = df['low'].rolling(window=tenkan_p).min()
    tenkan = (tenkan_h + tenkan_l) / 2

    # Kijun-sen (Base Line): (26-period high + 26-period low) / 2
    kijun_h = df['high'].rolling(window=kijun_p).max()
    kijun_l = df['low'].rolling(window=kijun_p).min()
    kijun = (kijun_h + kijun_l) / 2

    # Senkou Span A (Leading Span A): (Tenkan + Kijun) / 2, shifted forward
    span_a = ((tenkan + kijun) / 2).shift(displace)

    # Senkou Span B (Leading Span B): (52-period high + 52-period low) / 2, shifted forward
    senkou_h = df['high'].rolling(window=senkou_p).max()
    senkou_l = df['low'].rolling(window=senkou_p).min()
    span_b = ((senkou_h + senkou_l) / 2).shift(displace)

    # Chikou Span (Lagging Span): Close shifted back
    chikou = df['close'].shift(-displace)

    # 4. Final Formatting and Rounding
    res = pd.DataFrame({
        'tenkan': tenkan.round(precision),
        'kijun': kijun.round(precision),
        'span_a': span_a.round(precision),
        'span_b': span_b.round(precision),
        'chikou': chikou.round(precision)
    }, index=df.index)
    
    # We drop rows where the Kijun (base trend) is not yet available
    return res.dropna(subset=['kijun'])