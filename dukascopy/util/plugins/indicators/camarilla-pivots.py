import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    return (
        "Camarilla Pivots provide 8 levels of support and resistance. "
        "The most critical levels are L3/H3 for mean reversion and L4/H4 for breakouts."
    )

def meta() -> Dict:
    return {
        "author": "Google Gemini",
        "version": 1.0,
        "panel": 0, # Overlays on price
        "verified": 1,
        "polars": 1
    }

def warmup_count(options: Dict[str, Any]) -> int:
    return 1 # Needs the previous bar

def position_args(args: List[str]) -> Dict[str, Any]:
    return {} # No parameters needed

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    h = pl.col("high").shift(1)
    l = pl.col("low").shift(1)
    c = pl.col("close").shift(1)
    r = h - l

    return [
        (c + r * (1.1 / 2)).alias(f"{indicator_str}__h4"),
        (c + r * (1.1 / 4)).alias(f"{indicator_str}__h3"),
        (c + r * (1.1 / 6)).alias(f"{indicator_str}__h2"),
        (c + r * (1.1 / 12)).alias(f"{indicator_str}__h1"),
        (c - r * (1.1 / 12)).alias(f"{indicator_str}__l1"),
        (c - r * (1.1 / 6)).alias(f"{indicator_str}__l2"),
        (c - r * (1.1 / 4)).alias(f"{indicator_str}__l3"),
        (c - r * (1.1 / 2)).alias(f"{indicator_str}__l4"),
    ]

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    h, l, c = df['high'].shift(1), df['low'].shift(1), df['close'].shift(1)
    r = h - l
    return pd.DataFrame({
        'h4': c + r * (1.1 / 2), 'h3': c + r * (1.1 / 4), 'h2': c + r * (1.1 / 6), 'h1': c + r * (1.1 / 12),
        'l1': c - r * (1.1 / 12), 'l2': c - r * (1.1 / 6), 'l3': c - r * (1.1 / 4), 'l4': c - r * (1.1 / 2)
    }, index=df.index).dropna()