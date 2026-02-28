import polars as pl
from typing import List, Dict, Any
import numpy as np

def description() -> str:
    return (
        "Rolling Correlation: Calculates the rolling Pearson correlation between two symbols "
        "over a specified period. Useful for detecting regime shifts when correlations "
        "deviate from their typical values.\n\n"
        "Note: some of these indicators will become system indicators soon."
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
    return int(options.get("period", 20)) * 3 + 50

def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "symbol1": args[0] if len(args) > 0 else "EUR-USD",
        "symbol2": args[1] if len(args) > 1 else "USD-CHF",
        "period": args[2] if len(args) > 2 else "20",           # Correlation lookback
        "indicator": args[3] if len(args) > 3 else "close",     # Price or indicator to use
        "indicator_period": args[4] if len(args) > 4 else None   # Optional period for indicator
    }

def calculate(df: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    from util.api import get_data
    from concurrent.futures import ThreadPoolExecutor

    # Parse options
    symbol1 = options.get("symbol1", "EUR-USD")
    symbol2 = options.get("symbol2", "USD-CHF")
    period = int(options.get("period", 20))
    indicator = options.get("indicator", "close")
    indicator_period = options.get("indicator_period")
    
    if indicator == "close":
        col_name = "close"
    elif indicator_period:
        col_name = f"{indicator}_{indicator_period}"
    else:
        col_name = indicator
    
    tf = df["timeframe"].item(0)
    time_min = df["time_ms"].min()
    time_max = df["time_ms"].max()
    
    warmup_ms = 86400000 * 45  
    api_opts = {**options, "return_polars": True}

    def fetch_symbol_data(symbol_name, label):
        indicators = [col_name]
        if "close" not in col_name:
            indicators.append("is-open")
        
        data = get_data(
            symbol=symbol_name,
            timeframe=tf,
            after_ms=time_min - warmup_ms,
            until_ms=time_max + 1,
            indicators=indicators,
            limit=1000000,
            options=api_opts
        )
        
        if data is None or data.is_empty():
            return pl.LazyFrame({"time_ms": [], label: []})
        
        lazy = data.lazy()
        if "close" not in col_name:
            lazy = lazy.filter(pl.col("is-open") == 0)
        
        return (
            lazy.select([
                pl.col("time_ms").cast(pl.UInt64),
                pl.col(col_name).alias(label)
            ]).sort("time_ms")
        )
    
    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(fetch_symbol_data, symbol1, "val1")
        f2 = executor.submit(fetch_symbol_data, symbol2, "val2")
        lazy1, lazy2 = f1.result(), f2.result()
    
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
    
    for i in range(period - 1, n):
        start = i - period + 1
        window1 = v1[start : i + 1]
        window2 = v2[start : i + 1]
        
        mask = ~(np.isnan(window1) | np.isnan(window2))
        u1, u2 = window1[mask], window2[mask]
        
        if len(u1) < max(period // 2, 5):
            continue
            
        std1, std2 = np.std(u1), np.std(u2)
        if std1 < 1e-8 or std2 < 1e-8:
            rolling_corr[i] = 0.0
        else:
            corr_matrix = np.corrcoef(u1, u2)
            rolling_corr[i] = corr_matrix[0, 1]
    
    return pl.DataFrame({
        "rolling_corr": pl.Series("rolling_corr", rolling_corr).fill_nan(None).fill_null(strategy="forward")
    })