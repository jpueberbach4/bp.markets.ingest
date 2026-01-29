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
| `indicators` | `List[str]` | List of indicator strings to calculate (e.g., `["sma_20", "bbands_20_2"]`). |
| `options` | `Dict` | Dictionary of additional options and modifiers (e.g., `{"modifiers": ["skiplast"]}`). |

## 5. Requirements

Python: 3.8+.

Libraries: numpy, pandas.

**The get_data import code is also available for you in the examples folder. You can just copy and paste the method into your external code.**

