import polars as pl
from typing import List, Dict, Any

def description() -> str:
    return (
        "ATR normalized for Machine Learning"
        ""
        "Tree-Based Models (XGBoost, Random Forest, LightGBM): Use standard NATR (zscore_window = 0). "
        "Decision trees do not care about the scale or distribution of the feature, they only care "
        "about rank ordering. NATR successfully strips out the absolute price dependency."
        ""
        "Neural Networks, SVMs, or Linear Models: Use the Rolling Z-Score (zscore_window = 50 or 100). "
        "These algorithms calculate gradients and distance metrics, requiring inputs to be strictly "
        "standardized (normally distributed around 0)."
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
    return window + zscore_window + 1

def warmup_count(options: Dict[str, Any]):
    return int(options.get('period', 50))

def calculate(df: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    """
    Calculates Normalized ATR (NATR) and an optional Rolling Z-Score of NATR.
    Returns only the newly computed columns.
    """
    window = int(options.get("window", 14))
    zscore_window = int(options.get("zscore_window", 0)) 
    
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
        col_name = f"atr_zscore_{window}_{zscore_window}"
    else:
        ml_feature = natr
        col_name = f"natr_{window}"
        
    return df.select([
        ml_feature.alias(col_name)
    ])