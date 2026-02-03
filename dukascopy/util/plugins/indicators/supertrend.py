import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    return "SuperTrend is a trend-following indicator based on ATR. It provides a clear floor (uptrend) or ceiling (downtrend) for price action."

def meta() -> Dict:
    return {"author": "Google Gemini", "version": 1.0, "panel": 0, "verified": 1, "polars": 0}

def warmup_count(options: Dict[str, Any]) -> int:
    return int(options.get('period', 10)) * 2

def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "period": args[0] if len(args) > 0 else "10",
        "multiplier": args[1] if len(args) > 1 else "3.0"
    }

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    p = int(options.get('period', 10))
    m = float(options.get('multiplier', 3.0))
    
    # Calculate basic ATR components
    hl2 = (pl.col("high") + pl.col("low")) / 2
    # Lazy ATR approximation for Polars expression efficiency
    atr = (pl.col("high") - pl.col("low")).rolling_mean(window_size=p)
    
    upper = hl2 + (m * atr)
    lower = hl2 - (m * atr)
    
    return [
        upper.alias(f"{indicator_str}__upper"),
        lower.alias(f"{indicator_str}__lower")
    ]

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    p = int(options.get('period', 10))
    m = float(options.get('multiplier', 3.0))
    hl2 = (df['high'] + df['low']) / 2
    # Standard ATR logic
    tr = pd.concat([df['high'] - df['low'], 
                    (df['high'] - df['close'].shift(1)).abs(), 
                    (df['low'] - df['close'].shift(1)).abs()], axis=1).max(axis=1)
    atr = tr.rolling(p).mean()
    return pd.DataFrame({'upper': hl2 + (m * atr), 'lower': hl2 - (m * atr)}, index=df.index)