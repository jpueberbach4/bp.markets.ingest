import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    return "Rolling Sharpe Ratio measures the risk-adjusted return of an asset over a specific window."

def meta() -> Dict:
    return {"author": "Google Gemini", "version": 1.0, "panel": 1, "verified": 1, "polars": 1}

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    p = int(options.get('period', 30))
    returns = pl.col("close").pct_change()
    
    sharpe = returns.rolling_mean(window_size=p) / returns.rolling_std(window_size=p)
    # Annualize (assuming daily data)
    sharpe_ann = sharpe * np.sqrt(252)
    
    return [sharpe_ann.alias(f"{indicator_str}__sharpe")]

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    p = int(options.get('period', 30))
    returns = df['close'].pct_change()
    sharpe = (returns.rolling(p).mean() / returns.rolling(p).std()) * np.sqrt(252)
    return pd.DataFrame({'sharpe': sharpe}, index=df.index)