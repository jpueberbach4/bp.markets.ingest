# Developer Guide: Inter-Dataset Indicators

## 1. Overview
Standard indicators (like SMA) only use the data provided in the current DataFrame slice. Inter-dataset indicators, however, need to fetch a **secondary** symbol to perform comparisons. 

By importing `util.api.get_data`, your plugin can request any other cached asset for the exact same time window currently being processed.

---

## 2. Implementation: Pearson Correlation Example
This example shows how to build a `pearson.py` plugin. It calculates the correlation between the current symbol and a target symbol (e.g., `pearson_US10Y_20`).

### Code Structure (plugins/pearson.py)

```python
import pandas as pd
import numpy as np
from typing import List, Dict, Any

# Import the core data fetcher
from util.api import get_data

def warmup_count(options: Dict[str, Any]) -> int:
    # Correlation needs a history buffer to be stable
    period = int(options.get('period', 20))
    return period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    # URL format: pearson_SYMBOL_PERIOD (e.g., pearson_US10Y_20)
    return {
        "target_symbol": args[0] if len(args) > 0 else "US10Y",
        "period": args[1] if len(args) > 1 else "20"
    }

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    target_symbol = options.get('target_symbol')
    period = int(options.get('period', 20))
    
    # 1. Determine the time window of the current primary slice
    after_ms = int(df['sort_key'].min())
    until_ms = int(df['sort_key'].max())
    timeframe = str(df['timeframe'].iloc[0])

    # 2. Fetch the external dataset
    # CRITICAL: Always pass indicators=[] to avoid infinite recursive loops
    external_df = get_data(
        symbol=target_symbol,
        timeframe=timeframe,
        after_ms=after_ms,
        until_ms=until_ms,
        indicators=[] 
    )

    if external_df.empty:
        return pd.DataFrame({f"corr_{target_symbol}": np.nan}, index=df.index)

    # 3. Synchronize via sort_key
    # Move external data to a time-based index for alignment
    external_df = external_df.set_index('sort_key')
    
    # 4. Perform the calculation
    # Since 'df' is already indexed by sort_key in the parallel engine, 
    # we can align them directly in a temporary DataFrame.
    combined = pd.DataFrame({
        'primary': df['close'],
        'external': external_df['close']
    })

    correlation = combined['primary'].rolling(window=period).corr(combined['external'])

    # 5. Return a DataFrame with the new indicator column
    return pd.DataFrame({
        f"corr_{target_symbol}_{period}": correlation
    }, index=df.index)

```

---

## 3. Critical Requirements

### A. Recursive Safety
* **The Danger:** If `pearson` calls `get_data` for `US10Y` with the `sma` indicator, and `sma` (if updated) calls something else, you could trigger a circular dependency or exhaust the ThreadPool, crashing the API. This is not yet an issue but when dependencies get supported, it is.

### B. Index Alignment via `sort_key`
Never assume row counts match between two symbols (e.g., Bond markets have different holidays than Forex). 
* Always use `sort_key` (epoch ms) as your alignment key. 
* The `parallel_indicators` engine expects your returned index to match the input `df.index` exactly. By using a join or shared index based on `sort_key`, you ensure accuracy.

### C. Performance
Each call to `get_data` involves a cache lookup. While the memory-mapped architecture is extremely fast (~5-15ms), keep these points in mind:
* `get_data` results are already pre-filtered by the time window you provide.
* The `THREAD_EXECUTOR` in `parallel.py` handles these external fetches concurrently across different indicator tasks.

---

## DOCUMENTATION SUBJECT TO CHANGE