import polars as pl
from typing import Dict, Any, List

def description() -> str:
    return (
        "ML-Ready Normalized RSI. Offers three specific normalization modes for different model types.\n"
        " • Mode 'center' [-1, 1]: Best for Deep Learning (LSTM/GRU/Transformer). Centers data around 0, mapping perfectly to tanh/sigmoid activations.\n"
        " • Mode 'minmax' [0, 1]: Best for Tree-based models (XGBoost/Random Forest). Preserves rank ordering while keeping scale uniform.\n"
        " • Mode 'zscore' (Std Dev): Best for Regime Change/Anomaly detection. Unlike 'minmax', this does not cap at 0 or 100, allowing the model to see extreme outlier events (e.g., 5-sigma moves)."
    )

def meta() -> Dict:
    return {
        "author": "Gemini",
        "version": 1.1,
        "panel": 1,
        "polars_input": 1,
        "category": "ML features"
    }

def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "window": args[0] if len(args) > 0 else "14",
        "zscore-window": args[1] if len(args) > 1 else "100",
        "mode": args[2] if len(args) > 2 else "minmax",
    }

def warmup_count(options: Dict[str, Any]) -> int:
    window = int(options.get("window", 14))
    mode = options.get("mode", "minmax").lower()
    zscore_window = int(options.get("zscore-window", 100))
    
    base_warmup = window * 3
    
    if mode == "zscore":
        return base_warmup + zscore_window
    
    return base_warmup

def calculate(df: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    window = int(options.get("window", 14))
    mode = options.get("mode", "minmax").lower() 
    zscore_window = int(options.get("zscore-window", 100))
    
    delta = pl.col("close").diff()
    up = delta.clip(lower_bound=0)
    down = delta.clip(upper_bound=0).abs()
    
    alpha = 1.0 / window
    avg_gain = up.ewm_mean(alpha=alpha, adjust=False, min_periods=window)
    avg_loss = down.ewm_mean(alpha=alpha, adjust=False, min_periods=window)
    
    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))
    
    if mode == "zscore":
        rolling_mean = rsi.rolling_mean(window_size=zscore_window)
        rolling_std = rsi.rolling_std(window_size=zscore_window)
        
        safe_std = pl.when(rolling_std == 0.0).then(1e-9).otherwise(rolling_std)
        
        normalized_rsi = (rsi - rolling_mean) / safe_std
        col_name = f"rsi_zscore"
        
    elif mode == "center":
        normalized_rsi = (rsi - 50.0) / 50.0
        col_name = f"rsi_center"
        
    else:
        normalized_rsi = rsi / 100.0
        col_name = f"rsi_scaled"

    return df.select([
        normalized_rsi.alias(col_name)
    ])