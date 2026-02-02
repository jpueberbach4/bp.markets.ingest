import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "The Parabolic SAR (Stop and Reverse) is a trend-following indicator used to "
        "identify potential reversals in price movement. It appears as a series of "
        "dots placed either above or below the price: dots below indicate a bullish "
        "trend, while dots above indicate a bearish trend. The indicator 'accelerates' "
        "as the trend continues, moving closer to the price to provide dynamic trailing "
        "stop-loss levels."
    )

def meta() -> Dict:
    """
    Metadata for the dual-engine orchestrator.
    """
    return {
        "author": "Google Gemini",
        "version": 1.1,
        "verified": 1,
        "polars": 1
    }

def warmup_count(options: Dict[str, Any]) -> int:
    """
    PSAR requires a warmup to establish the correct trend direction and 
    acceleration factor stability. 100 bars is the industry standard.
    """
    return 100

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: psar_0.02_0.2 -> {'step': '0.02', 'max_step': '0.2'}
    """
    return {
        "step": args[0] if len(args) > 0 else "0.02",
        "max_step": args[1] if len(args) > 1 else "0.2"
    }

def _psar_backend(highs: np.ndarray, lows: np.ndarray, step: float, max_step: float) -> np.ndarray:
    """
    Internal NumPy state machine for recursive PSAR calculation.
    """
    n = len(highs)
    psar = np.zeros(n)
    bull = True 
    af = step
    ep = highs[0]
    psar[0] = lows[0]

    for i in range(1, n):
        prev_psar = psar[i-1]
        
        if bull:
            psar[i] = prev_psar + af * (ep - prev_psar)
            psar[i] = min(psar[i], lows[i-1], lows[max(0, i-2)])
            
            if lows[i] < psar[i]:
                bull = False
                psar[i] = ep
                ep = lows[i]
                af = step
            else:
                if highs[i] > ep:
                    ep = highs[i]
                    af = min(af + step, max_step)
        else:
            psar[i] = prev_psar + af * (ep - prev_psar)
            psar[i] = max(psar[i], highs[i-1], highs[max(0, i-2)])
            
            if highs[i] > psar[i]:
                bull = True
                psar[i] = ep
                ep = highs[i]
                af = step
            else:
                if lows[i] < ep:
                    ep = lows[i]
                    af = min(af + step, max_step)
    return psar

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> pl.Expr:
    """
    High-performance Polars-native calculation for PSAR.
    Uses map_batches to execute the recursive state machine in a single pass.
    """
    try:
        step = float(options.get('step', 0.02))
        max_step = float(options.get('max_step', 0.2))
    except (ValueError, TypeError):
        step, max_step = 0.02, 0.2

    # We use pl.struct to pass multiple columns (high/low) to the NumPy backend
    return pl.struct(["high", "low"]).map_batches(
        lambda s: _psar_backend(
            s.struct.field("high").to_numpy(),
            s.struct.field("low").to_numpy(),
            step, 
            max_step
        )
    ).round(5).alias(indicator_str)

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    Legacy fallback for Pandas-only environments.
    """
    try:
        step = float(options.get('step', 0.02))
        max_step = float(options.get('max_step', 0.2))
    except (ValueError, TypeError):
        step, max_step = 0.02, 0.2

    try:
        sample_price = str(df['close'].iloc[0])
        precision = len(sample_price.split('.')[1])+1 if '.' in sample_price else 2
    except (IndexError, AttributeError):
        precision = 5

    highs = df['high'].values
    lows = df['low'].values
    psar_values = _psar_backend(highs, lows, step, max_step)

    res = pd.DataFrame({
        'psar': psar_values
    }, index=df.index)
    
    return res.round(precision)