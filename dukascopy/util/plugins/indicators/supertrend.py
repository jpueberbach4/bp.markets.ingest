import pandas as pd
import numpy as np
import polars as pl
from typing import List, Dict, Any

def description() -> str:
    return "SuperTrend is a trend-following indicator based on ATR. It provides a clear floor (uptrend) or ceiling (downtrend) for price action."

def meta() -> Dict:
    return {"author": "Google Gemini", "version": 2.1, "panel": 0, "verified": 1, "polars": 0, "polars_input":1}

def warmup_count(options: Dict[str, Any]) -> int:
    return int(options.get('period', 10)) * 2

def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "period": args[0] if len(args) > 0 else "10",
        "multiplier": args[1] if len(args) > 1 else "3.0"
    }


def calculate(ldf: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    # 1. Extract columns to Numpy for performance 🏎️
    # using .to_numpy() is zero-copy where possible
    high = ldf["high"].to_numpy()
    low = ldf["low"].to_numpy()
    close = ldf["close"].to_numpy()
    
    p = int(options.get('period', 10))
    m = float(options.get('multiplier', 3.0))
    n = len(close)

    # 2. Vectorized Pre-calculation (ATR & Basic Bands) ⚡
    # We use numpy for the pre-calc to keep data in the same format
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]
    
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)))
    tr[0] = high[0] - low[0] # Handle first row
    
    # Calculate ATR using a simple moving average (matching your pandas logic)
    # We can use a fast convolution for the rolling mean
    if n >= p:
        kernel = np.ones(p) / p
        atr = np.convolve(tr, kernel, mode='same')
        # Fix the boundary effect of convolve to match pandas rolling
        atr[:p-1] = 0 
        # Note: For exact pandas parity, we might need a more specific rolling function, 
        # but this is the fastest numpy-native way.
    else:
        atr = np.zeros(n)

    hl2 = (high + low) / 2
    basic_upper = hl2 + (m * atr)
    basic_lower = hl2 - (m * atr)

    # 3. The Recursive Loop (The "SuperTrend" Logic) 🔄
    final_upper = np.zeros(n)
    final_lower = np.zeros(n)
    supertrend = np.zeros(n)
    trend = 1 
    
    # Initialize first row
    final_upper[0] = basic_upper[0]
    final_lower[0] = basic_lower[0]
    supertrend[0] = final_lower[0]

    # Standard python loop - fast enough when run once per dataset
    for i in range(1, n):
        # Final Upper
        if basic_upper[i] < final_upper[i-1] or close[i-1] > final_upper[i-1]:
            final_upper[i] = basic_upper[i]
        else:
            final_upper[i] = final_upper[i-1]
        
        # Final Lower
        if basic_lower[i] > final_lower[i-1] or close[i-1] < final_lower[i-1]:
            final_lower[i] = basic_lower[i]
        else:
            final_lower[i] = final_lower[i-1]
        
        # Trend Logic
        if trend == 1:
            if close[i] < final_lower[i]:
                trend = -1
                supertrend[i] = final_upper[i]
            else:
                supertrend[i] = final_lower[i]
        else:
            if close[i] > final_upper[i]:
                trend = 1
                supertrend[i] = final_lower[i]
            else:
                supertrend[i] = final_upper[i]

    # 4. Return as Polars DataFrame 📦
    return pl.DataFrame({
        "value": supertrend,
        "direction": trend,
        "upper_guard": final_upper,
        "lower_guard": final_lower
    })

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    p = int(options.get('period', 10))
    m = float(options.get('multiplier', 3.0))

    def apply_supertrend(s: pl.Series) -> pl.Series:
        # FIX: Unpack the Struct Series using .struct.field()
        high = s.struct.field("high").to_numpy()
        low = s.struct.field("low").to_numpy()
        close = s.struct.field("close").to_numpy()
        
        n = len(close)
        
        prev_close = np.roll(close, 1)
        prev_close[0] = close[0]
        
        tr = np.maximum(high - low, np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)))
        tr[0] = high[0] - low[0]
        
        if n >= p:
            kernel = np.ones(p) / p
            atr = np.convolve(tr, kernel, mode='same')
            atr = pd.Series(tr).rolling(p).mean().fillna(0).values
        else:
            atr = np.zeros(n)

        hl2 = (high + low) / 2
        basic_upper = hl2 + (m * atr)
        basic_lower = hl2 - (m * atr)
        
        final_upper = np.zeros(n)
        final_lower = np.zeros(n)
        supertrend = np.zeros(n)
        trend = 1 # 1 = Up, -1 = Down
        
        final_upper[0] = basic_upper[0]
        final_lower[0] = basic_lower[0]
        supertrend[0] = final_lower[0]
        
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
                    
        return pl.Series(supertrend)

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
    
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)))
    
    atr = pd.Series(tr).rolling(p).mean().fillna(0).values
    
    hl2 = (high + low) / 2
    basic_upper = hl2 + (m * atr)
    basic_lower = hl2 - (m * atr)
    
    final_upper = np.zeros(n)
    final_lower = np.zeros(n)
    supertrend = np.zeros(n)
    trend = 1 
    
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
                
    return pd.DataFrame({
        'value': supertrend,
        'direction': trend,
        'upper_guard': final_upper,
        'lower_guard': final_lower
    }, index=df.index)