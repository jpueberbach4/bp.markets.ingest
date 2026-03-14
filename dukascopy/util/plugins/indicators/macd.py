import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    return "Independent MACD using native Polars SMA-seeding for EMA initialization."

def meta() -> Dict:
    return {"author": "Google Gemini", "version": 1.4, "panel": 1, "verified": 1, "talib-validated":1, "polars": 1}

def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "fast": args[0] if len(args) > 0 else "12",
        "slow": args[1] if len(args) > 1 else "26",
        "signal": args[2] if len(args) > 2 else "9"
    }

def _ema_talib_logic(series: pl.Expr, period: int) -> pl.Expr:
    """Matches TA-Lib EMA behavior using only Polars: SMA seed at index period-1."""
    return (
        pl.when(series.cum_count() <= period)
        .then(series.head(period).mean())
        .otherwise(series)
        .ewm_mean(span=period, adjust=False)
    )

def warmup_count(options: Dict[str, Any]) -> int:
    # Slow EMA lookback + signal EMA lookback for stable outputs
    return int(options.get('slow', 26)) + int(options.get('signal', 9))

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    fast = int(options.get('fast', 12))
    slow = int(options.get('slow', 26))
    sig = int(options.get('signal', 9))

    ema_fast = _ema_talib_logic(pl.col("close"), fast)
    ema_slow = _ema_talib_logic(pl.col("close"), slow)
    macd_line = ema_fast - ema_slow
    
    macd_masked = pl.when(pl.col("close").cum_count() < slow).then(None).otherwise(macd_line)

    signal_line = _ema_talib_logic(macd_masked, sig)
    
    total_lookback = (slow - 1) + (sig - 1)
    final_signal = pl.when(pl.col("close").cum_count() <= total_lookback).then(None).otherwise(signal_line)
    
    return [
        macd_masked.alias(f"{indicator_str}__macd"),
        final_signal.alias(f"{indicator_str}__signal"),
        (macd_masked - final_signal).alias(f"{indicator_str}__hist")
    ]

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """Pure NumPy/Pandas fallback (No TA-Lib import)."""
    f, s, sig = int(options.get('fast', 12)), int(options.get('slow', 26)), int(options.get('signal', 9))
    ema_f = df['close'].ewm(span=f, adjust=False).mean()
    ema_s = df['close'].ewm(span=s, adjust=False).mean()
    macd = ema_f - ema_s
    signal = macd.ewm(span=sig, adjust=False).mean()
    return pd.DataFrame({'macd': macd, 'signal': signal, 'hist': macd - signal}, index=df.index)