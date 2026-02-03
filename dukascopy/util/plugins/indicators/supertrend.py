import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    """
    SuperTrend is a trend-following indicator. It switches between a lower support line (uptrend)
    and an upper resistance line (downtrend) based on price crossovers.
    """
    return "SuperTrend: A switching trend indicator that acts as a trailing stop based on ATR."

def meta() -> Dict:
    return {
        "author": "Google Gemini",
        "version": 2.0,
        "panel": 0,
        "verified": 1,
        "polars": 1 # Now fully implemented via map_batches
    }

def warmup_count(options: Dict[str, Any]) -> int:
    return int(options.get('period', 10)) * 2

def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "period": args[0] if len(args) > 0 else "10",
        "multiplier": args[1] if len(args) > 1 else "3.0"
    }

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    p = int(options.get('period', 10))
    m = float(options.get('multiplier', 3.0))

    def apply_supertrend(df_slice: pl.DataFrame) -> pl.Series:
        # Convert to numpy for fast looping
        high = df_slice["high"].to_numpy()
        low = df_slice["low"].to_numpy()
        close = df_slice["close"].to_numpy()
        
        n = len(close)
        
        # 1. Calculate ATR (Simple Rolling Mean approximation for speed in the loop)
        # For precision, we pre-calc TR outside, but here we do it inline or expect it passed.
        # Let's do a simple TR calculation here.
        tr = np.maximum(high - low, np.maximum(np.abs(high - np.roll(close, 1)), np.abs(low - np.roll(close, 1))))
        tr[0] = high[0] - low[0]
        
        # Simple Moving Average for ATR to match standard SuperTrend behavior
        # (Recursive Wilder's smoothing is ideal but SMA is standard in many libs)
        atr = np.zeros(n)
        s = pd.Series(tr) # Pandas rolling is cleaner for this part inside the batch
        atr = s.rolling(p).mean().fillna(0).values

        # 2. Basic Bands
        hl2 = (high + low) / 2
        basic_upper = hl2 + (m * atr)
        basic_lower = hl2 - (m * atr)
        
        # 3. Recursive Final Bands
        final_upper = np.zeros(n)
        final_lower = np.zeros(n)
        supertrend = np.zeros(n)
        trend = 1 # 1 = Up, -1 = Down
        
        for i in range(1, n):
            # Final Upper Logic
            if basic_upper[i] < final_upper[i-1] or close[i-1] > final_upper[i-1]:
                final_upper[i] = basic_upper[i]
            else:
                final_upper[i] = final_upper[i-1]
                
            # Final Lower Logic
            if basic_lower[i] > final_lower[i-1] or close[i-1] < final_lower[i-1]:
                final_lower[i] = basic_lower[i]
            else:
                final_lower[i] = final_lower[i-1]
                
            # Trend Switch Logic
            if trend == 1:
                supertrend[i] = final_lower[i]
                if close[i] < final_lower[i]:
                    trend = -1
                    supertrend[i] = final_upper[i]
            else:
                supertrend[i] = final_upper[i]
                if close[i] > final_upper[i]:
                    trend = 1
                    supertrend[i] = final_lower[i]
                    
        return pl.Series(supertrend)

    # Pass the struct of required columns to map_batches
    return [
        pl.struct(["high", "low", "close"])
        .map_batches(apply_supertrend)
        .alias(f"{indicator_str}__value")
    ]

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    p = int(options.get('period', 10))
    m = float(options.get('multiplier', 3.0))
    
    high = df['high'].values
    low = df['low'].values
    close = df['close'].values
    n = len(close)
    
    # ATR Calc
    tr = np.maximum(high - low, np.maximum(np.abs(high - np.roll(close, 1)), np.abs(low - np.roll(close, 1))))
    tr[0] = high[0] - low[0]
    atr = pd.Series(tr).rolling(p).mean().fillna(0).values
    
    hl2 = (high + low) / 2
    basic_upper = hl2 + (m * atr)
    basic_lower = hl2 - (m * atr)
    
    final_upper = np.zeros(n)
    final_lower = np.zeros(n)
    supertrend = np.zeros(n)
    trend = 1 
    
    # Standard SuperTrend Loop
    for i in range(1, n):
        if basic_upper[i] < final_upper[i-1] or close[i-1] > final_upper[i-1]:
            final_upper[i] = basic_upper[i]
        else:
            final_upper[i] = final_upper[i-1]
            
        if basic_lower[i] > final_lower[i-1] or close[i-1] < final_lower[i-1]:
            final_lower[i] = basic_lower[i]
        else:
            final_lower[i] = final_lower[i-1]
            
        if trend == 1:
            supertrend[i] = final_lower[i]
            if close[i] < final_lower[i]:
                trend = -1
                supertrend[i] = final_upper[i]
        else:
            supertrend[i] = final_upper[i]
            if close[i] > final_upper[i]:
                trend = 1
                supertrend[i] = final_lower[i]
                
    # Return 3 columns: The main line, plus the raw bands if needed for debugging
    return pd.DataFrame({
        'value': supertrend,
        'direction': trend, # Helpful for bots: 1=Buy, -1=Sell
        'upper_guard': final_upper,
        'lower_guard': final_lower
    }, index=df.index)