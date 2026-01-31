# Integrating the Internal Dukascopy API: A Developer's Guide 

This guide provides the necessary steps to integrate the `get_data` API from the `bp.markets.ingest` repository into external Python projects. Because this API is designed as part of a specific directory hierarchy, it requires a **bootstrap** approach to resolve its internal dependencies.

"This is the way"-would the mandolorian say- to currently include the internal-api of `bp.markets.ingest` in your external code. While not yet a formal library (Librarization is on the roadmap), this bootstrap method provides a robust, high-performance link to the core engine.

## 1. API Architecture Overview

The `api.py` module acts as the high-performance gateway to the Dukascopy data pipeline. Key features include:

* **Data Retrieval**: Efficiently slices OHLCV data from cached memory-mapped datasets.
* **Automated Indicators**: Supports computation of technical indicators (e.g., `sma`, `rsi`) with automatic handling of warmup rows.
* **Parallel Processing**: Optionally utilizes parallelization for indicator calculations to maximize throughput.
* **Normalized Output**: Returns a standard Pandas DataFrame containing `symbol`, `timeframe`, `time_ms`, OHLCV, and indicator columns.

## 2. The Bootstrap Pattern

Due to internal relative imports (e.g., `from util.cache import ...`), standard Python imports from external directories will result in a `ModuleNotFoundError`. The following function injects the required root paths into `sys.path` and dynamically loads the module.

### Implementation

```python
import importlib.util
import sys
import os

def bootstrap_bp_api(
    api_path: str = "/home/repos/bp.markets.ingest/dukascopy/util/api.py",
    root_dir: str = "/home/repos/bp.markets.ingest/dukascopy"
):
    """Bootstraps and returns the internal `get_data` API function.

    This function dynamically loads a local API module from disk, ensures
    required local dependencies can be resolved, and returns the module's
    `get_data` function. The loaded module is cached in `sys.modules` to
    prevent repeated loading.

    Args:
        api_path: Absolute path to the API Python file to load.
        root_dir: Root directory to add to `sys.path` for resolving
            local imports used by the API module.

    Returns:
        Callable: The `get_data` function defined in the loaded API module.

    Raises:
        ImportError: If the API module cannot be located at `api_path`.
        RuntimeError: If execution of the API module fails.
    """
    # Ensure local imports inside the API module can be resolved
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

    # Internal module name used for caching in sys.modules
    module_name = "api_internal"

    # Return cached function if the module has already been loaded
    if module_name in sys.modules:
        return sys.modules[module_name].get_data

    # Create an import spec for dynamically loading the module from disk
    spec = importlib.util.spec_from_file_location(module_name, api_path)
    if spec is None:
        raise ImportError(f"Could not locate the API file at: {api_path}")

    # Create a new module object from the spec
    api_module = importlib.util.module_from_spec(spec)

    # Register the module early to support nested imports during execution
    sys.modules[module_name] = api_module

    try:
        # Execute the module in its own namespace
        spec.loader.exec_module(api_module)
    except Exception as e:
        # Remove the partially loaded module to allow clean retries
        if module_name in sys.modules:
            del sys.modules[module_name]
        raise RuntimeError(f"Failed to execute API module: {e}") from e

    # Expose the API entrypoint
    return api_module.get_data


# --- Execution ---
try:
    get_data = bootstrap_bp_api()
    print("🚀 Internal get_data successfully linked and ready for high-performance retrieval.")
except Exception as e:
    print(f"❌ Bootstrap failed: {e}")



```

## 3. Usage Example
Once the function is bootstrapped, you can query data using standard arguments.

```python

# Link the API
get_data = bootstrap_bp_api()

# Retrieve data with indicators
df = get_data(
    symbol="EUR-USD",
    timeframe="1m",
    after_ms=1704067200000, 
    limit=1000,
    indicators=["sma_20", "rsi_14"]
)

print(df.head())
```

### 4. API Reference: `get_data`

| Argument | Type | Description |
| :--- | :--- | :--- |
| `symbol` | `str` | The trading symbol (e.g., "EURUSD"). |
| `timeframe` | `str` | The OHLCV timeframe (e.g., "1m", "5m"). |
| `after_ms` | `int` | Inclusive lower bound timestamp in epoch milliseconds. |
| `until_ms` | `int` | Exclusive upper bound timestamp in epoch milliseconds. |
| `limit` | `int` | Maximum rows to return (default: 1000). |
| `order` | `str` | Order of the returned data-slice (default: asc). Other value: desc |
| `indicators` | `List[str]` | List of indicator strings to calculate (e.g., `["sma_20", "bbands_20_2"]`). |
| `options` | `Dict` | Dictionary of additional options and modifiers (e.g., `{"modifiers": ["skiplast"]}`). |

## 5. Requirements

Python: 3.8+.

Libraries: numpy, pandas.

**The get_data import code is also available for you in the examples folder. You can just copy and paste the method into your external code.**

## 6. Performance Benchmarks

The engine is engineered for **Hyperparameter Optimization (HPO)** and large-scale backtesting. By leveraging memory-mapped file access, the API achieves throughput that significantly outperforms traditional database setups.

### Throughput Comparison - 1,000,000 rows
| Query Type | Throughput | Performance Note |
| :--- | :--- | :--- |
| **Price-Only (Raw)** | **~3,000,000+ rows/sec** | Zero-copy memory mapped retrieval. |
| **Heavy Load (500 Indicators)** | **~650,000 rows/sec** | **0.5 Billion datapoints processed in 1.5s**. |
| **Light Load (5 Indicators)** | **~1,600,000 rows/sec** | Minimal overhead, purely IO bound. |

### Why this matters:
* **Research Speed**: A researcher can test **1,000 different indicator combinations** in under **3.5 minutes**. 
* **Comparison**: The same task on a standard relational database or CSV-based setup would typically take 30+ minutes.
* **Efficiency**: As chunk sizes increase, the overhead of the Python function call is minimized, allowing the engine to reach its theoretical maximum speed.

> **Pro Tip**: The first query to `get_data` includes a one-time overhead for indicator registry loading. For accurate benchmarking, always discard the first "cold" run.

This project enables: Try crazy ideas "just to see". Don't worry about the compute. Its fast.

What is my crazy idea? I have an CSV with all bottoms manually marked on the H4. I am going to feed a model 
1000's of indicator values and have it find the best combinations that match those bottoms. I train on 2020-2023 and walk-forward, do an out-of-sample test, on 2024 and 2025 (for which i also marked the bottoms manually). I will find a golden combination. Question is, how long will it be valid until it becomes invalid.

```python
import pandas as pd
import numpy as np
from util.api import get_data
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix

indicators = []

for window in range(5, 200, 5):
    indicators.append(f"rsi_{window}")
    indicators.append(f"sma_{window}")
    indicators.append(f"ema_{window}")
    indicators.append(f"atr_{window}")
    indicators.append(f"adx_{window}")

for window in [10, 20, 50]:
    for std in [2.0, 2.5, 3.0]:
        indicators.append(f"bbands_{window}_{std}")

indicators.append("macd_12_26_9")
indicators.append("macd_24_52_18")

print(f"🚀 Generated {len(indicators)} feature definitions.")

print("⏳ Fetching Data & Calculating Features...")
df = get_data(
    symbol="EUR-USD",
    timeframe="4h",
    after_ms=1577836800000,
    limit=100000,
    indicators=indicators
)
print(f"✅ Loaded {len(df)} rows with {len(df.columns)} columns.")

labels = pd.read_csv("my_manual_bottoms.csv")
labels['is_bottom'] = 1

df = df.merge(labels[['time_ms', 'is_bottom']], on='time_ms', how='left')
df['is_bottom'] = df['is_bottom'].fillna(0)

df.dropna(inplace=True)

split_time = 1704067200000

train = df[df['time_ms'] < split_time]
test = df[df['time_ms'] >= split_time]

X_train = train.drop(columns=['symbol', 'timeframe', 'time_ms', 'is_bottom'])
y_train = train['is_bottom']

X_test = test.drop(columns=['symbol', 'timeframe', 'time_ms', 'is_bottom'])
y_test = test['is_bottom']

print(f"Training on {len(train)} candles (2020-2023)")
print(f"Testing on {len(test)} candles (2024-2025)")

clf = RandomForestClassifier(
    n_estimators=100,
    n_jobs=-1,
    class_weight='balanced',
    random_state=42
)
clf.fit(X_train, y_train)

print("\n=== OUT OF SAMPLE RESULTS (2024-2025) ===")
preds = clf.predict(X_test)
print(classification_report(y_test, preds))

importances = pd.Series(clf.feature_importances_, index=X_train.columns)
print("\n=== TOP 10 INDICATORS FOR BOTTOMS ===")
print(importances.sort_values(ascending=False).head(10))


```

note: the above is a very simplified example. my real trainer has nearly everything i could think of. including candle geometry and linking to the dxy and bonds, both usbond as well as bund/gilt. i will think about it to release it. releasing it wont cause damage since the classes are used to SUPPORT training. not the actual model application. i think i will do it when its done. or a slightly stripped version may get published. this part is not done yet... i will be working on it for at least another two weeks to make it "fully capable".
