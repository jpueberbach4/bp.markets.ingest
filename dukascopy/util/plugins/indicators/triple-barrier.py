import polars as pl
from typing import List, Dict, Any

def description() -> str:
    return (
        "Triple Barrier Bounds (Lopez de Prado): Calculates dynamic volatility-based "
        "Take-Profit (Upper) and Stop-Loss (Lower) barriers on the price chart."
    )

def meta() -> Dict:
    return {
        "author": "Google Gemini",
        "version": 1.1,
        "panel": 0, # Overlay directly on the price chart safely
        "verified": 1,
        "polars": 1,
        "polars_expr": 1
    }

def warmup_count(options: Dict[str, Any]) -> int:
    vol_period = int(options.get("vol_period", 60))
    return vol_period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "vol_period": args[0] if len(args) > 0 else "60",     
        "pt_multiplier": args[1] if len(args) > 1 else "2.0", 
        "sl_multiplier": args[2] if len(args) > 2 else "1.0"  
    }

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    vol_period = int(options.get("vol_period", 60))
    pt_mult = float(options.get("pt_multiplier", 2.0))
    sl_mult = float(options.get("sl_multiplier", 1.0))

    returns = pl.col("close") / pl.col("close").shift(1) - 1.0
    volatility = returns.ewm_std(span=vol_period, adjust=False)

    upper_barrier = pl.col("close") * (1.0 + (volatility * pt_mult))
    lower_barrier = pl.col("close") * (1.0 - (volatility * sl_mult))

    return [
        upper_barrier.fill_null(strategy="forward").alias(f"{indicator_str}__upper_pt"),
        lower_barrier.fill_null(strategy="forward").alias(f"{indicator_str}__lower_sl")
    ]