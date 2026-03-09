import polars as pl
from typing import List, Dict, Any

def description() -> str:
    return (
        "Coppock Curve: A long-term momentum oscillator. "
        "Formula: WMA(ROC_Long + ROC_Short). Updated for Polars 1.25+."
    )

def meta() -> Dict:
    return {
        "author": "Google Gemini",
        "version": 1.2,
        "panel": 1,
        "verified": 1,
        "polars": 1
    }

def warmup_count(options: Dict[str, Any]) -> int:
    rl = int(options.get('roc_long', 14))
    w = int(options.get('wma_period', 10))
    return rl + w + 50

def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "roc_long": args[0] if len(args) > 0 else "14",
        "roc_short": args[1] if len(args) > 1 else "11",
        "wma_period": args[2] if len(args) > 2 else "10"
    }

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    rl = int(options.get('roc_long', 14))
    rs = int(options.get('roc_short', 11))
    w = int(options.get('wma_period', 10))

    roc_l = (pl.col("close") / pl.col("close").shift(rl) - 1)
    roc_s = (pl.col("close") / pl.col("close").shift(rs) - 1)
    
    coppock_raw = (roc_l + roc_s) * 100

    weights = list(range(1, w + 1))
    w_sum = sum(weights)
    
    def _wma_logic(s: pl.Series) -> pl.Series:
        import numpy as np
        v = s.to_numpy()
        if len(v) < w:
            return pl.Series([None] * len(v), dtype=pl.Float64)
        
        res = np.convolve(v, np.array(weights)[::-1], mode='valid') / w_sum
        return pl.Series(np.concatenate([np.full(w - 1, np.nan), res]), dtype=pl.Float64)

    return [
        coppock_raw.rolling_map(
            _wma_logic, 
            window_size=w,
        )
        .fill_nan(None)
        .alias(f"{indicator_str}__value")
    ]
