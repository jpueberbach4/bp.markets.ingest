import polars as pl
from typing import List, Dict, Any

def description() -> str:
    return (
        "Divergence Detector: Measures normalized divergence between two symbols. "
        "Calculates z-score of the relative strength difference between Symbol 1 and Symbol 2.\n"
    )

def meta() -> Dict:
    return {
        "author": "JP",
        "version": "1.0",
        "panel": 1,
        "verified": 1,
        "polars": 0,
        "polars_input": 1,
        "nocheck":1
    }

def warmup_count(options: Dict[str, Any]) -> int:
    return int(options.get("period", 20)) + 50

def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "symbol1": args[0] if len(args) > 0 else "EUR-USD",
        "symbol2": args[1] if len(args) > 1 else "DOLLAR.IDX-USD",
        "period": args[2] if len(args) > 2 else "20",
        "indicator": args[3] if len(args) > 3 else "rsi",
        "indicator_period": args[4] if len(args) > 4 else "14"
    }

def calculate(df: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    from util.api import get_data
    from concurrent.futures import ThreadPoolExecutor
    import numpy as np

    # Parse options
    symbol1 = options.get("symbol1", "EUR-USD")
    symbol2 = options.get("symbol2", "DOLLAR.IDX-USD")
    period = int(options.get("period", 20))
    indicator = options.get("indicator", "rsi")
    indicator_period = options.get("indicator_period", "14")
    
    indicator_col = f"{indicator}_{indicator_period}"
    
    # Global Physics Parity: Use input TF and time range
    tf = df["timeframe"].item(0)
    time_min = df["time_ms"].min()
    time_max = df["time_ms"].max()
    
    api_opts = {**options, "return_polars": True}
    warmup_ms = 86400000 * 30  # 30 days for indicator stability

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
    
    # UNIFY TIMELINE
    timeline = df.select([pl.col("time_ms").cast(pl.UInt64)]).lazy()
    
    merged = (
        timeline
        .join_asof(lazy1, on="time_ms", strategy="backward")
        .join_asof(lazy2, on="time_ms", strategy="backward")
        .collect()
    )

    v1 = merged["val1"]
    v2 = merged["val2"]
    
    v1_norm = (v1 - v1.rolling_mean(period)) / (v1.rolling_std(period) + 1e-8)
    v2_norm = (v2 - v2.rolling_mean(period)) / (v2.rolling_std(period) + 1e-8)
    
    raw_divergence = v1_norm - v2_norm
    
    mean = raw_divergence.rolling_mean(period)
    std = raw_divergence.rolling_std(period)
    zscore = (raw_divergence - mean) / (std + 1e-8)
    
    return pl.DataFrame({
        "divergence": zscore.fill_nan(0).fill_null(0)
    })