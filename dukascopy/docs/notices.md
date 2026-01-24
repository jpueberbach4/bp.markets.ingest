<u>MT4 is decoded.</u>

What's next?

- Final round of public development
- Stabilization
- Private and public version
- Replay/Market simulation
- Relaunch

### Notice: really have to say

Now I am really working on the prediction part, this is really insanely powerful. Especially the last version (not yet released). You can for example put moving averages over RSI, do interdata queries with indicators. And it all. stays. fast. 

You can do something like this on the new version:

```python
import pandas as pd
import numpy as np
from typing import List, Dict, Any
 
def description() -> str:
    """
    Identifies market bottoms using Volume Climax, Lower Wick Absorption, 
    and Price Exhaustion (Distance from EMA 200).
    """
    return (
        "Bottom Sniper is a reversal-seeking indicator. It fires a signal when "
        "forced liquidations (Volume Climax) meet heavy aggressive buying "
        "(Wick Absorption) at prices significantly extended below the 200 EMA."
    )

def meta() -> Dict:
    return {
        "author": "XXXGoogle Gemini",
        "version": 1.1,
        "panel": 1,
        "verified": 1 
    }

def warmup_count(options: Dict[str, Any]) -> int:
    # Requires 200 bars for EMA 200 stability
    return 600

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    from util.api import get_data

    # 1. Metadata & Data Fetching
    symbol, timeframe = df.iloc[0].symbol, df.iloc[0].timeframe
    after_ms, until_ms, limit = df.iloc[0].time_ms, df.iloc[-1].time_ms, len(df)

    rsi_setting = 'rsi_7'
    streak_setting = 3
    oversold_setting = 30
    sma_window = 8

    indicators = [rsi_setting]
    ex_df = get_data(symbol, timeframe, after_ms, until_ms + 1, limit, "asc", indicators, {'disable_recursive_mapping': True})

    # Moving Average Calculation
    ex_df['sma'] = ex_df[rsi_setting].rolling(window=sma_window).mean()

    # Suppression Logic
    # Check if RSI is below SMA 9
    is_below_sma = ex_df[rsi_setting] < ex_df['sma']
    
    # Use rolling sum to find at least 5 consecutive bars where this is true
    # We use .fillna(0) to handle the first few bars of the data
    suppression_streak = is_below_sma.rolling(window=5).sum().fillna(0)
    
    print(suppression_streak)

    # Signal Trigger
    # Trigger if we have a streak of AT LEAST 5 AND current bar is oversold (< 30)
    # This captures the 5th bar and every bar after that stays suppressed
    is_bottom_signal = (suppression_streak >= streak_setting) & (ex_df[rsi_setting] < oversold_setting)

    print(is_bottom_signal)

    # 5. Result Mapping
    results_df = pd.DataFrame({
        'time_ms': ex_df['time_ms'],
        'rsi': ex_df[rsi_setting],
        'sma': ex_df['sma'],
        'is_bottom': np.where(is_bottom_signal, 100, 0)
    })

    final_res = df[['time_ms']].merge(results_df, on='time_ms', how='left').set_index(df.index)
    
    return final_res[['rsi', 'sma', 'is_bottom']]
```

### Notice: clean-version is in the making

I am currently working on the clean-version. This version has undergone another major refactor. It now supports an internal API and performance was pushed even a little bit more. The price-only API has now latency of about 3-5ms(1m, random 2020 date, 1000 records). With 3 indicators-ema,sma,macd-it now pushes around 10ms. That is core-api call. Without the JSON response. Wall time. I will finish this off ASAP and launch it pretty soon. Max 2 weekends away.

Price-only API pushes now ~1.8 million bars per second. 10.000 in ~6ms. Without serialization. This is the max for Python.

### Bonus ML Example: Bottom Detection with Random Forest

this works not oke. building new one

