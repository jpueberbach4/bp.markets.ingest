import polars as pl
from typing import Dict, Any, List

def description() -> str:
    return (
        "RSI normalized for Machine Learning (MinMax [0,1], Centered [-1,1], or Z-Score)."
        ""
        "For LSTM / GRU / Transformers: Use mode=\"center\". These networks initialize weights "
        "expecting inputs around 0. The [-1, 1] range maps perfectly to the tanh activation "
        "functions often used internally."
        ""
        "For Random Forest / XGBoost: Use mode=\"minmax\" (or even raw RSI). Trees don't struggle "
        " with uncentered data, but scaling to 0-1 keeps your features uniform."
        ""
        "For \"Regime Change\" Models: Use mode=\"zscore\". If you are trying to predict market "
        "tops/bottoms, a Z-Score of +2.0 is often a stronger signal than just \"RSI=75\", because "
        "it tells you the RSI is statistically unusually high relative to the current volatility."
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
        "mode": args[2] if len(args) > 2 else "minmax",
    }

def warmup_count(options: Dict[str, Any]) -> int:
    window = int(options.get("window", 14))
    zscore_window = int(options.get("zscore-window", 0))
    return (window * 3) + zscore_window

def calculate(df: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    """
    Calculates RSI and normalizes it for ML usage.
    Options:
      - window: RSI period (default 14)
      - mode: 'minmax' (0..1), 'center' (-1..1), 'zscore' (std dev from mean)
      - zscore_window: Rolling window for Z-score (only used if mode='zscore')
    """
    window = int(options.get("window", 14))
    mode = options.get("mode", "minmax").lower() # minmax, center, zscore
    zscore_window = int(options.get("zscore_window", 100))
    
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
        col_name = f"rsi_{window}_zscore_{zscore_window}"
        
    elif mode == "center":
        normalized_rsi = (rsi - 50.0) / 50.0
        col_name = f"rsi_{window}_centered"
        
    else:
        normalized_rsi = rsi / 100.0
        col_name = f"rsi_{window}_scaled"

    return df.select([
        normalized_rsi.alias(col_name)
    ])