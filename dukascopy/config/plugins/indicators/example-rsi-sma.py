import pandas as pd
from typing import List, Dict, Any

def description() -> str:
    return (
        "Non-Talib RSI with SMA Smoothing. Uses get_data_auto to fetch the base "
        "RSI and applies a vectorized SMA overlay on the RSI. Pandas example."
    )

def meta() -> Dict:
    return {
        "author": "Google Gemini",
        "version": 1.8,
        "panel": 1,
        "verified": 1,
        "polars": 0
    }

def warmup_count(options: Dict[str, Any]) -> int:
    rsi_period = int(options.get('rsi_period', 14))
    sma_period = int(options.get('sma_period', 9))
    return (rsi_period * 3) + sma_period

def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "rsi_period": args[0] if len(args) > 0 else "14",
        "sma_period": args[1] if len(args) > 1 else "9"
    }


def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    Vectorized Pandas implementation using get_data_auto for modularity.
    Returns both RSI and SMA for panel plotting.
    """
    from util.api import get_data_auto, get_data

    rsi_period = int(options.get('rsi_period', 14))
    sma_period = int(options.get('sma_period', 9))

    rsi_col = f"rsi_{rsi_period}"
    sma_col = f'sma_{sma_period}'
    ex_df = get_data_auto(df, indicators=[rsi_col])

    ex_df[sma_col] = ex_df[rsi_col].rolling(window=sma_period).mean()

    return ex_df[[rsi_col, sma_col]]