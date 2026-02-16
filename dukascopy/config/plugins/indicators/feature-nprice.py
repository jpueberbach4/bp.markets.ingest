import polars as pl
from typing import Dict, Any, List

def description() -> str:
    return (
        "Normalizer for price. Transforms raw prices into machine-learning friendly features.\n"
        " • Mode 'log': Logarithmic Returns (Stationary). Best for forecasting direction/volatility (e.g., LSTM, Transformer). Eliminates price levels.\n"
        " • Mode 'minmax': Rolling MinMax (0.0-1.0). Best for Mean Reversion/Sniping. Preserves 'cheap' vs 'expensive' context relative to the window.\n"
        " • Mode 'zscore': Rolling Z-Score (Std Dev). Best for Anomaly Detection. Unbounded (does not saturate) to detect extreme breakouts."
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
        "target-col": args[1] if len(args) > 1 else "close",
        "mode": args[2] if len(args) > 2 else "log",
    }

def warmup_count(options: Dict[str, Any]) -> int:
    mode = options.get("mode", "log")
    window = int(options.get("window", 20))
    
    if mode == "minmax":
        return window
    else:
        return 2

def calculate(df: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    mode = options.get("mode", "log").lower()
    window = int(options.get("window", 20))
    target_col = options.get("target-col", "close") 
    
    if mode == "log":
        log_price = pl.col(target_col).log()
        normalized = log_price.diff()
        col_name = f"{target_col}_log"

    elif mode == "minmax":
        rolling_min = pl.col(target_col).rolling_min(window_size=window)
        rolling_max = pl.col(target_col).rolling_max(window_size=window)
        
        denominator = (rolling_max - rolling_min).replace(0, 0.0001) # Safety
        
        normalized = (pl.col(target_col) - rolling_min) / denominator
        col_name = f"{target_col}_minmax"
    elif mode == "zscore":
        rolling_mean = pl.col(target_col).rolling_mean(window_size=window)
        rolling_std = pl.col(target_col).rolling_std(window_size=window)
        
        safe_std = rolling_std.replace(0.0, 1e-9)
        
        normalized = (pl.col(target_col) - rolling_mean) / safe_std
        col_name = f"{target_col}_zscore"
        
    else:
        raise ValueError(f"Unknown mode: {mode}")

    return df.select([
        normalized.alias(col_name)
    ])