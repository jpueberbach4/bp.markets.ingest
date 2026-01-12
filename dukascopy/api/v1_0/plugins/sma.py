import pandas as pd
import numpy as np
from typing import List, Dict, Any

def position_args(args: List[str]) -> Dict[str, Any]:
    return {"period": args[0]} if args else {}

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    try:
        period = int(options.get('period', 14))
    except (ValueError, TypeError):
        period = 14

    # Calculate rolling mean
    sma = df['close'].rolling(window=period).mean()

    # Determine precision for rounding
    sample_price = str(df['close'].iloc[0])
    precision = len(sample_price.split('.')[1]) if '.' in sample_price else 5
    
    return pd.DataFrame({'sma': sma.round(precision)}, index=df.index).dropna()