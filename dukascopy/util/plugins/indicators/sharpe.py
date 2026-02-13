import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    return "Rolling Sharpe Ratio measures risk-adjusted returns (Excess Return / Volatility)."

def meta() -> Dict:
    return {"author": "Google Gemini", "version": 1.2, "panel": 1, "verified": 1, "polars": 1}

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps: sharpe/period/risk_free/annualization
    Example: sharpe/30/0.02/252
    """
    return {
        "period": args[0] if len(args) > 0 else "30",
        "rf": args[1] if len(args) > 1 else "0.0",
        "annual": args[2] if len(args) > 2 else "252"
    }

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    p = int(options.get('period', 30))
    rf = float(options.get('rf', 0.0))
    ann = float(options.get('annual', 252))
    
    returns = pl.col("close").pct_change()
    
    excess_return = returns - (rf / ann)
    
    sharpe = excess_return.rolling_mean(window_size=p) / returns.rolling_std(window_size=p, ddof=0)
    
    sharpe_ann = sharpe * np.sqrt(ann)
    
    return [sharpe_ann.alias(f"{indicator_str}__sharpe")]

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    p = int(options.get('period', 30))
    rf = float(options.get('rf', 0.0))
    ann = float(options.get('annual', 252))
    
    returns = df['close'].pct_change()
    excess = returns - (rf / ann)
    
    sharpe = (excess.rolling(p).mean() / returns.rolling(p).std(ddof=0)) * np.sqrt(ann)
    return pd.DataFrame({'sharpe': sharpe}, index=df.index)