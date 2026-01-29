"""
"This is the way" to currently include the internal-api of bp.markets.ingest in your external code.

Ofcourse it may not be optimal since we all are used to module's, pip install etc,... 

But it works very well for our purpose. Librarization will happen someday. When not sick, when all the
other features are done and when we have plenty of time.

This solves the problem. Just copy this bootstrap_bp_api routine into an include within your external
code and it will work.

"""
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


# -----------------------------------------------------------------------------
# Now we can start querying
# -----------------------------------------------------------------------------
from datetime import datetime, timezone
import time
# Convert the timestring
timestamp_str = "2025-11-17+19:00:00"
dt = datetime.strptime(timestamp_str, "%Y-%m-%d+%H:%M:%S")
after_ms = int(dt.replace(tzinfo=timezone.utc).timestamp() * 1000)


start = time.perf_counter()
indicators = ['adx_14', 'atr_14', 'ema_20', 'bbands_20_2.0', 'macd_12_26_9']
df = get_data(symbol="EUR-USD", timeframe="1m", indicators=indicators, after_ms=after_ms, limit=10000, order="asc" )
print(f"10.000 records, time-passed: {(time.perf_counter()-start)*1000} + 5 indicators\n\n")

print(df)


