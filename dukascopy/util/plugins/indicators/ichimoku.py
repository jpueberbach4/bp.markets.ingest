import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "The Ichimoku Cloud (Ichimoku Kinko Hyo) defines support and resistance, "
        "identifies trend direction, and gauges momentum. It consists of five lines: "
        "Tenkan-sen, Kijun-sen, Senkou Span A/B (the Cloud), and Chikou Span."
    )

def meta() -> Dict:
    """
    Metadata for the dual-engine orchestrator.
    """
    return {
        "author": "Google Gemini",
        "version": 1.1,
        "verified": 1,
        "polars": 1,  # Trigger high-speed Polars execution path
        "needs": "surface-colouring"
    }

def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for Ichimoku Cloud.
    """
    try:
        kijun_p = int(options.get('kijun', 26))
        senkou_p = int(options.get('senkou', 52))
        displace = int(options.get('displacement', kijun_p))
    except (ValueError, TypeError):
        senkou_p, displace = 52, 26

    return (senkou_p + displace) * 2

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    """
    return {
        "tenkan": args[0] if len(args) > 0 else "9",
        "kijun": args[1] if len(args) > 1 else "26",
        "senkou": args[2] if len(args) > 2 else "52"
    }

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    """
    High-performance Polars-native calculation using Lazy expressions.
    """
    try:
        tenkan_p = int(options.get('tenkan', 9))
        kijun_p = int(options.get('kijun', 26))
        senkou_p = int(options.get('senkou', 52))
        displace = int(options.get('displacement', kijun_p))
    except (ValueError, TypeError):
        tenkan_p, kijun_p, senkou_p, displace = 9, 26, 52, 26

    # 1. Tenkan-sen (9-period high + 9-period low) / 2
    tenkan = (pl.col("high").rolling_max(window_size=tenkan_p) + 
              pl.col("low").rolling_min(window_size=tenkan_p)) / 2

    # 2. Kijun-sen (26-period high + 26-period low) / 2
    kijun = (pl.col("high").rolling_max(window_size=kijun_p) + 
             pl.col("low").rolling_min(window_size=kijun_p)) / 2

    # 3. Senkou Span A (Leading Span A): (Tenkan + Kijun) / 2, shifted forward
    span_a = ((tenkan + kijun) / 2).shift(displace)

    # 4. Senkou Span B (Leading Span B): (52-period high + 52-period low) / 2, shifted forward
    span_b = ((pl.col("high").rolling_max(window_size=senkou_p) + 
               pl.col("low").rolling_min(window_size=senkou_p)) / 2).shift(displace)

    # 5. Chikou Span (Lagging Span): Close shifted back
    chikou = pl.col("close").shift(-displace)

    # Return as aliased expressions for the nested orchestrator
    return [
        tenkan.alias(f"{indicator_str}__tenkan"),
        kijun.alias(f"{indicator_str}__kijun"),
        span_a.alias(f"{indicator_str}__span_a"),
        span_b.alias(f"{indicator_str}__span_b"),
        chikou.alias(f"{indicator_str}__chikou")
    ]

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    Legacy Pandas fallback.
    """
    try:
        tenkan_p = int(options.get('tenkan', 9))
        kijun_p = int(options.get('kijun', 26))
        senkou_p = int(options.get('senkou', 52))
        displace = int(options.get('displacement', kijun_p))
    except (ValueError, TypeError):
        tenkan_p, kijun_p, senkou_p, displace = 9, 26, 52, 26

    tenkan = (df['high'].rolling(window=tenkan_p).max() + df['low'].rolling(window=tenkan_p).min()) / 2
    kijun = (df['high'].rolling(window=kijun_p).max() + df['low'].rolling(window=kijun_p).min()) / 2
    span_a = ((tenkan + kijun) / 2).shift(displace)
    span_b = ((df['high'].rolling(window=senkou_p).max() + df['low'].rolling(window=senkou_p).min()) / 2).shift(displace)
    chikou = df['close'].shift(-displace)

    return pd.DataFrame({
        'tenkan': tenkan,
        'kijun': kijun,
        'span_a': span_a,
        'span_b': span_b,
        'chikou': chikou
    }, index=df.index).dropna(subset=['kijun'])