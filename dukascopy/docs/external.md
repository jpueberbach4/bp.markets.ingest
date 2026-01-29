# Integrating the Internal Dukascopy API: A Developer's Guide 

This guide provides the necessary steps to integrate the `get_data` API from the `bp.markets.ingest` repository into external Python projects. Because this API is designed as part of a specific directory hierarchy, it requires a **bootstrap** approach to resolve its internal dependencies.

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
    api_path: str = "/home/jpueberb/repos2/bp.markets.ingest/dukascopy/util/api.py",
    root_dir: str = "/home/jpueberb/repos2/bp.markets.ingest/dukascopy"
):
    """
    Bootstraps the get_data API and resolves internal dependencies.

    Args:
        api_path: Absolute path to the api.py file.
        root_dir: The 'dukascopy' folder (parent of the 'util' package).
    """
    # 1. Add the directory containing the 'util' folder to sys.path
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

    # 2. Prevent repeated loading by caching in sys.modules
    module_name = "api_internal"
    if module_name in sys.modules:
        return sys.modules[module_name].get_data

    # 3. Create a spec and load the module from disk
    spec = importlib.util.spec_from_file_location(module_name, api_path)
    if spec is None:
        raise ImportError(f"Could not locate the API file at: {api_path}")

    api_module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = api_module

    try:
        spec.loader.exec_module(api_module)
    except Exception as e:
        if module_name in sys.modules:
            del sys.modules[module_name]
        raise RuntimeError(f"Failed to execute API module: {e}")

    return api_module.get_data
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
| `indicators` | `List[str]` | List of indicator strings to calculate (e.g., `["sma_20", "bbands_20_2"]`). |
| `options` | `Dict` | Dictionary of additional options and modifiers (e.g., `{"modifiers": ["skiplast"]}`). |

## 5. Requirements

Python: 3.8+.

Libraries: numpy, pandas.

**The get_data import code is also available for you in the examples folder. You can just copy and paste the method into your external code.**

