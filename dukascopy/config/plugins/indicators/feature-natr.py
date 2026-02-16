import polars as pl
from typing import List, Dict, Any

def description() -> str:
    return (
        "ML-Ready Normalized ATR (NATR). Measures volatility relative to price.\n"
        " • Standard NATR (zscore-window=0): Volatility as % of Close. Best for Tree-Based models (XGBoost, RF) which handle raw scaling well.\n"
        " • Z-Score NATR (zscore-window>0): Rolling Z-Score of NATR. Best for Neural Networks/Linear Models requiring strictly standardized inputs (mean 0, std 1)."
    )

def meta() -> Dict:
    return {
        "author": "Gemini",
        "version": 1.0,
        "panel": 1,
        "polars_input": 1,
        "category": "ML features"
    }

def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "window": args[0] if len(args) > 0 else "14",
        "zscore-window": args[1] if len(args) > 1 else "0",
    }

def warmup_count(options: Dict[str, Any]) -> int:
    window = int(options.get("window", 14))
    zscore_window = int(options.get("zscore-window", 0))
    stabilization_period = window * 3
    return stabilization_period + zscore_window

def calculate(df: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    window = int(options.get("window", 14))
    zscore_window = int(options.get("zscore-window", 0)) 
    
    prev_close = pl.col("close").shift(1)
    
    tr = pl.max_horizontal([
        pl.col("high") - pl.col("low"),
        (pl.col("high") - prev_close).abs(),
        (pl.col("low") - prev_close).abs()
    ])
    
    atr = tr.ewm_mean(alpha=1.0/window, adjust=False)
    
    natr = (atr / pl.col("close")) * 100.0
    
    if zscore_window > 0:
        rolling_mean = natr.rolling_mean(window_size=zscore_window)
        rolling_std = natr.rolling_std(window_size=zscore_window)
        
        safe_std = pl.when(rolling_std == 0.0).then(1e-9).otherwise(rolling_std)
        
        ml_feature = (natr - rolling_mean) / safe_std
        col_name = f"atr_zscore"
    else:
        ml_feature = natr
        col_name = f"atr_norm"
        
    return df.select([
        ml_feature.alias(col_name)
    ])