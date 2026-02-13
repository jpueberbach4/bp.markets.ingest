import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    return "Plots the nearest key round-number (Psychological Level) directly on the price chart."

def meta() -> Dict:
    return {
        "author": "Google Gemini",
        "version": 1.1,
        "panel": 0,
        "verified": 1,
        "polars": 1
    }

def warmup_count(options: Dict[str, Any]) -> int:
    return 1

def position_args(args: List[str]) -> Dict[str, Any]:
    return {"grid": args[0] if len(args) > 0 else "1.0"} 

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    try:
        grid = float(options.get('grid', 1.0))
    except (ValueError, TypeError):
        grid = 1.0
    
    closest_level = (pl.col("close") / grid).round(0) * grid
    
    return [
        closest_level.alias(f"{indicator_str}__level")
    ]

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    try:
        grid = float(options.get('grid', 1.0))
    except (ValueError, TypeError):
        grid = 1.0
        
    closest = (df['close'] / grid).round() * grid
    
    return pd.DataFrame({
        'level': closest
    }, index=df.index)