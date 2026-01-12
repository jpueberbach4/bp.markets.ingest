import pandas as pd
import numpy as np
from typing import List, Dict, Any

def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "period": args[0] if len(args) > 0 else "20",
        "std": args[1] if len(args) > 1 else "2.0"
    }

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    try:
        period = int(options.get('period', 20))
        std_dev = float(options.get('std', 2.0))
    except (ValueError, TypeError):
        period, std_dev = 20, 2.0

    mid = df['close'].rolling(window=period).mean()
    rolling_std = df['close'].rolling(window=period).std()
    
    upper = mid + (rolling_std * std_dev)
    lower = mid - (rolling_std * std_dev)

    sample_price = str(df['close'].iloc[0])
    precision = len(sample_price.split('.')[1]) if '.' in sample_price else 5
    
    res = pd.DataFrame({
        'upper': upper.round(precision),
        'mid': mid.round(precision),
        'lower': lower.round(precision)
    }, index=df.index)
    
    return res.dropna()