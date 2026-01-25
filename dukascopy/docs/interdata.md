# Developer Guide: Inter-Dataset Indicators

## 1. Overview
Standard indicators (like SMA) only use the data provided in the current DataFrame slice. Inter-dataset indicators, however, need to fetch a **secondary** symbol to perform comparisons. 

By importing `util.api.get_data`, your plugin can request any other cached asset for the exact same time window currently being processed.

---

## 2. Implementation: Pearson Correlation Example
This example shows how to build a `pearson.py` plugin. It calculates the correlation between the current symbol and a target symbol (e.g., `pearson_US10Y_20`).

### Code Structure - Pseudo code

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
    
    # Fetch external data
    external_df = get_data(symbol=target_symbol, indicators=[], ...)

    if external_df.empty:
        return pd.DataFrame({f"corr_{target_symbol}": np.nan}, index=df.index)

    # Both DataFrames must be sorted by the key for merge_asof
    # They are already sorted, but for demonstration purposes we sort again
    df = df.sort_values('time_ms')
    external_df = external_df.sort_values('time_ms')

    # Use merge_asof to align external data to the primary timeframe
    # direction='backward' (default) takes the last known price of the external asset
    aligned_df = pd.merge_asof(
        df[['time_ms', 'close']], 
        external_df[['time_ms', 'close']], 
        on='time_ms', 
        suffixes=('', '_ext'),
        direction='backward'
    )

    # Calculate correlation on the aligned columns
    correlation = aligned_df['close'].rolling(window=period).corr(aligned_df['close_ext'])

    # Map back to original index
    results_df = pd.DataFrame({
        f"corr_{target_symbol}": correlation.values
    }, index=df.index)

    return results_df

```

### Unaligned data eg because of opening hours or different origin settings

In order to correlate data that doesnt align perfectly because of different opening hours or origin settings, use merge_asof.

`pd.merge_asof` is a specialized join designed for time-series data that aligns records based on the nearest key rather than requiring an exact match. It effectively handles datasets with different frequencies or unsynchronized timestamps by looking backward from the left frame to the most recent available value in the right frame. This makes it an essential tool in finance for correlating assets from different exchanges or timeframes without creating missing values due to minor clock drifts.

---

## 3. Critical Requirements

### A. Recursive Safety
* **The Danger:** If `pearson` calls `get_data` for `US10Y` with the `sma` indicator, and `sma` (if updated) calls something else, you could trigger a circular dependency or exhaust the ThreadPool, crashing the API. This is not yet an issue but when dependencies get supported, it is.

### B. Index Alignment via `time_ms`
Never assume row counts match between two symbols (e.g., Bond markets have different holidays than Forex). 
* Always use `time_ms` (epoch ms) as your alignment key. 
* The `parallel_indicators` engine expects your returned index to match the input `df.index` exactly. By using a join or shared index based on `time_ms`, you ensure accuracy.

### C. Performance
Each call to `get_data` involves a cache lookup. While the memory-mapped architecture is extremely fast (~2-5ms), keep these points in mind:
* `get_data` results are already pre-filtered by the time window you provide.
* `get_data` results are already sorted by `time_ms` regarding to the order specified
* `get_data` results EXCLUDE any warmup rows if queried with indicators
* `get_data` executes indicators. Don't ask for indicators you dont use in order to maintain efficiency and performance.
* The `THREAD_EXECUTOR` in `parallel.py` handles these external fetches concurrently across different indicator tasks.
