import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    return "Donchian Channel Width measures the range between the highest high and lowest low over N periods."

def meta() -> Dict:
    return {"author": "Google Gemini", "version": 1.1, "panel": 1, "verified": 1, "polars": 1}

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps: donchian-width/20 -> {'period': '20'}
    """
    return {
        "period": args[0] if len(args) > 0 else "20"
    }

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    p = int(options.get('period', 20))
    # Donchian High and Low
    hh = pl.col("high").rolling_max(window_size=p)
    ll = pl.col("low").rolling_min(window_size=p)
    
    # Calculation: (High - Low) / Center
    width = (hh - ll) / ((hh + ll) / 2)
    
    return [width.alias(f"{indicator_str}__width")]

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    p = int(options.get('period', 20))
    hh = df['high'].rolling(p).max()
    ll = df['low'].rolling(p).min()
    width = (hh - ll) / ((hh + ll) / 2)
    return pd.DataFrame({'width': width}, index=df.index).dropna()