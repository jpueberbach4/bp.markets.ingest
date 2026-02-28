import polars as pl
from typing import List, Dict, Any

def description() -> str:
    return (
        "Rolling Correlation Break Detector: Measures when the correlation between two symbols "
        "breaks down significantly. Returns a z-score of correlation deviation from its recent mean. "
        "Positive values indicate correlation strengthening, negative values indicate correlation breaking.\n"
    )

def meta() -> Dict:
    return {
        "author": "JP",
        "version": "1.0",
        "panel": 1,
        "verified": 1,
        "polars": 0,
        "polars_input": 1
    }

def warmup_count(options: Dict[str, Any]) -> int:
    return int(options.get("period", 20)) * 3 + 100

def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "symbol1": args[0] if len(args) > 0 else "EUR-USD",
        "symbol2": args[1] if len(args) > 1 else "DOLLAR.IDX-USD",
        "period": args[2] if len(args) > 2 else "20",           # Correlation lookback
        "lookback": args[3] if len(args) > 3 else "50",         # Mean reversion lookback
        "indicator": args[4] if len(args) > 4 else "rsi",
        "indicator_period": args[5] if len(args) > 5 else "14"
    }

def calculate(df: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    from util.api import get_data
    from concurrent.futures import ThreadPoolExecutor
    import numpy as np

    # Parse options
    symbol1 = options.get("symbol1", "EUR-USD")
    symbol2 = options.get("symbol2", "DOLLAR.IDX-USD")
    period = int(options.get("period", 20))           # Correlation window
    lookback = int(options.get("lookback", 50))       # Mean reversion window
    indicator = options.get("indicator", "rsi")
    indicator_period = options.get("indicator_period", "14")
    
    indicator_col = f"{indicator}_{indicator_period}"
    
    tf = df["timeframe"].item(0)
    time_min = df["time_ms"].min()
    time_max = df["time_ms"].max()
    
    api_opts = {**options, "return_polars": True}
    warmup_ms = 86400000 * 60  # 60 days for correlation stability

    def fetch_symbol_data(symbol_name, label):
        data = get_data(
            symbol=symbol_name,
            timeframe=tf,
            after_ms=time_min - warmup_ms,
            until_ms=time_max + 1,
            indicators=[indicator_col, "is-open"],
            limit=1000000,
            options=api_opts
        )
        
        if data is None or data.is_empty():
            return pl.LazyFrame({"time_ms": [], label: []})
        
        return (
            data.lazy()
            .filter(pl.col("is-open") == 0)
            .select([
                pl.col("time_ms").cast(pl.UInt64),
                pl.col(indicator_col).alias(label)
            ])
            .sort("time_ms")
        )
    
    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(fetch_symbol_data, symbol1, "val1")
        f2 = executor.submit(fetch_symbol_data, symbol2, "val2")
        
        lazy1 = f1.result()
        lazy2 = f2.result()
    
    timeline = df.select([pl.col("time_ms").cast(pl.UInt64)]).lazy()
    
    merged = (
        timeline
        .join_asof(lazy1, on="time_ms", strategy="backward")
        .join_asof(lazy2, on="time_ms", strategy="backward")
        .collect()
    )

    v1 = merged["val1"].to_numpy()
    v2 = merged["val2"].to_numpy()
    n = len(v1)
    
    rolling_corr = np.full(n, np.nan)
    corr_zscore = np.full(n, 0.0)
    
    for i in range(period - 1, n):
        start = max(0, i - period + 1)
        window1 = v1[start:i+1]
        window2 = v2[start:i+1]
        
        if len(window1) < period // 2 or len(window2) < period // 2:
            continue
            
        if np.std(window1) < 1e-8 or np.std(window2) < 1e-8:
            rolling_corr[i] = 0.0
        else:
            corr_matrix = np.corrcoef(window1, window2)
            rolling_corr[i] = corr_matrix[0, 1]
    
    for i in range(lookback + period - 1, n):
        start = max(0, i - lookback + 1)
        corr_window = rolling_corr[start:i+1]
        
        valid_mask = ~np.isnan(corr_window)
        if valid_mask.sum() < lookback // 2:
            continue
            
        valid_corrs = corr_window[valid_mask]
        mean_corr = np.mean(valid_corrs)
        std_corr = np.std(valid_corrs)
        
        if std_corr > 1e-8:
            corr_zscore[i] = (rolling_corr[i] - mean_corr) / std_corr
    
    typical_correlation = -0.8  # Configurable based on pair
    break_intensity = np.full(n, 0.0)
    for i in range(period - 1, n):
        if not np.isnan(rolling_corr[i]):
            # How far from typical correlation (normalized)
            break_intensity[i] = (rolling_corr[i] - typical_correlation) / (1 - abs(typical_correlation) + 1e-8)
    
    combined_signal = -corr_zscore * break_intensity  # Negative z-score * positive break = positive signal
    
    return pl.DataFrame({
        "correlation": rolling_corr,           # Raw rolling correlation
        "correlation_zscore": corr_zscore,     # Deviation from recent mean
        "break_intensity": break_intensity,     # How far from typical correlation
        "correlation_break": combined_signal    # Combined bottom detection signal
    })