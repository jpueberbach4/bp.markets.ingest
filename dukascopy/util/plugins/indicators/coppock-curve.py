import polars as pl
from typing import List, Dict, Any

def description() -> str:
    return (
        "Coppock Curve: A long-term momentum oscillator. "
        "Formula: WMA(ROC_Long + ROC_Short). Optimized for Native Polars performance."
    )

def meta() -> Dict:
    return {
        "author": "Google Gemini",
        "version": 1.3,
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

    # Calculate ROCs
    roc_l = (pl.col("close") / pl.col("close").shift(rl) - 1)
    roc_s = (pl.col("close") / pl.col("close").shift(rs) - 1)
    
    # CRITICAL: Fill nulls/NaNs with 0 before the weighted rolling sum
    # The panic happens because 'weights' doesn't support nulls yet.
    coppock_raw = ((roc_l + roc_s) * 100).fill_null(0).fill_nan(0)

    weights = [float(i) for i in range(1, w + 1)]
    w_sum = sum(weights)
    
    # This will now run without panicking
    coppock_wma = (
        coppock_raw.rolling_sum(window_size=w, weights=weights) / w_sum
    )

    return [
        coppock_wma.alias(f"{indicator_str}__value")
    ]