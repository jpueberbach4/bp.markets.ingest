import polars as pl
import pandas as pd
from typing import List, Dict, Any

def description() -> str:
    return "Standard Deviation quantifies price dispersion from its moving average."

def meta() -> Dict:
    return {"author": "Google Gemini", "version": 1.2, "verified": 1, "panel": 1, "talib-validated": 1, "polars": 1}

def position_args(args: List[str]) -> Dict[str, Any]:
    return {"period": args[0] if len(args) > 0 else "20"}

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> pl.Expr:
    p = int(options.get('period', 20))
    return pl.col("close").rolling_std(window_size=p, ddof=0).alias(indicator_str)

def calculate(df: Any, options: Dict[str, Any]) -> Any:
    p = int(options.get('period', 20))
    std_dev = df['close'].rolling(window=p, ddof=0).std()
    return pd.DataFrame({'std_dev': std_dev}, index=df.index).dropna()