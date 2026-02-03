import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    return "Volatility Ratio measures the spread of Bollinger Bands relative to Keltner Channels to identify 'Squeezes'."

def meta() -> Dict:
    return {"author": "Google Gemini", "version": 1.0, "panel": 1, "verified": 1, "polars": 1}

def warmup_count(options: Dict[str, Any]) -> int:
    return int(options.get('period', 20)) * 2

def position_args(args: List[str]) -> Dict[str, Any]:
    return {"period": args[0] if len(args) > 0 else "20"}

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    p = int(options.get('period', 20))
    
    # BBand Width component (2 std dev)
    std = pl.col("close").rolling_std(window_size=p)
    bb_width = std * 4
    
    # Keltner component (1.5 ATR)
    tr = pl.max_horizontal([(pl.col("high") - pl.col("low")), (pl.col("high") - pl.col("close").shift(1)).abs()])
    atr = tr.rolling_mean(window_size=p)
    kc_width = atr * 3
    
    ratio = bb_width / kc_width
    return [ratio.alias(f"{indicator_str}__ratio")]

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    p = int(options.get('period', 20))
    bb_w = df['close'].rolling(p).std() * 4
    tr = pd.concat([df['high'] - df['low'], (df['high'] - df['close'].shift(1)).abs()], axis=1).max(axis=1)
    kc_w = tr.rolling(p).mean() * 3
    return pd.DataFrame({'ratio': bb_w / kc_w}, index=df.index).dropna()