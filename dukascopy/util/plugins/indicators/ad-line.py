import polars as pl
from typing import List, Dict, Any

def description() -> str:
    return (
        "Synthetic Advance-Decline Line: Calculates cumulative market breadth "
        "using price change and volume as a proxy for advancing/declining pressure."
    )

def meta() -> Dict:
    return {
        "author": "Google Gemini",
        "version": "1.2",
        "panel": 1,
        "verified": 1,
        "polars": 1,
    }

def warmup_count(options: Dict[str, Any]) -> int:
    return 1

def position_args(args: List[str]) -> Dict[str, Any]:
    return {}

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    price_diff = pl.col("close").diff()
    
    weight = pl.when(pl.col("volume") > 0).then(pl.col("volume")).otherwise(1.0)
    
    daily_ad = (
        pl.when(price_diff > 0).then(weight)
        .when(price_diff < 0).then(weight * -1)
        .otherwise(0)
    )

    return [
        daily_ad.fill_null(0).cum_sum().alias(f"{indicator_str}__ad_line")
    ]