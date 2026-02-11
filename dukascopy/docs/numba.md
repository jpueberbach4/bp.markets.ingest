# Developer Guide: High-Performance Indicators with Numba JIT

This guide outlines the standard architecture for implementing high-performance technical indicators within the ingestion engine. Follow these patterns to ensure code is compiled to machine speed while remaining compatible with the parallel execution environment.

**VERIFICATION: PENDING!**

## Why Numba JIT?

While Polars is exceptionally fast for vectorized operations, certain indicators are **recursive** (row $i$ depends on $i-1$) or involve **heavy nested looping** (like Volume/Market Profiles). 

Numba translates a subset of Python and NumPy code into fast machine code. Using the patterns below, we achieve C-level performance while maintaining Python's maintainability.

---

## 🏗 The Dual-Module Architecture

To avoid serialization (pickling) errors like `ModuleNotFoundError: No module named '<dynamic>'` and to leverage disk caching, you must separate logic into two files.

### 1. The Static Backend (`config.user/plugins/indicators/helpers/{indicator}_backend.py`)
This file contains the "heavy lifting" logic. It must be a standard Python file in a package directory.

**Requirements:**
* **Decorator:** Use `@numba.jit(nopython=True, cache=True)`.
* **Standard Package:** The directory must contain an `__init__.py` file.
* **No Python Objects:** Use only NumPy arrays and primitive scalars (floats/ints).

[Image of Just-In-Time compilation workflow]

```python
# File: config.user/plugins/indicators/helpers/psar_backend.py
import numba
import numpy as np

@numba.jit(nopython=True, cache=True)
def _psar_backend(highs, lows, step, max_step):
    n = len(highs)
    psar = np.zeros(n)
    # ... recursive state machine logic ...
    for i in range(1, n):
        # Numba excels at these sequential loops
        psar[i] = psar[i-1] + ... 
    return psar
```

### 2. The Dynamic Plugin (config.user/plugins/indicators/{name}.py)
This is the entry point loaded by the engine. It handles parameter parsing and Polars integration.

Requirements:

Serialization: Use functools.partial instead of lambda to wrap the mapper.

Schema Safety: Always provide a return_dtype (usually pl.Float64 or pl.Struct) to map_batches.

Flat Output: Return a List[pl.Expr] for indicators with multiple outputs (e.g., POC, VAH, VAL).

```python
import importlib.util
import sys
import os

# This is a bit hacky (config.user contains a dot):
def register_backend(module_name: str, file_path: str):
    """
    Registers a file as a module in sys.modules to bypass folder naming issues.
    """
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

# Register your backends
base_path = os.getcwd()
register_backend(
    "psar_backend", 
    os.path.join(base_path, "config.user/plugins/indicators/helpers/psar_backend.py")
)

import polars as pl
from functools import partial

# We can now import using the virtual alias
from psar_backend import _psar_backend

def _map_wrapper(s: pl.Series, step: float, max_step: float) -> pl.Series:
    # Convert Polars struct/series to numpy for the JIT backend
    res = psar_calc_jit(s.struct.field("high").to_numpy(), ...)
    return pl.Series(res)

def calculate_polars(indicator_str: str, options: dict) -> pl.Expr:
    # Use partial for pickling safety in parallel workers
    mapper = partial(_map_wrapper, step=0.02, max_step=0.2)
    
    return (
        pl.struct(["high", "low"])
        .map_batches(mapper, return_dtype=pl.Float64)
        .alias(indicator_str)
    )
```

### 3. 🔑 Critical Rules for Developers

1. **cache=True** Requirement
The compilation penalty is ~200ms. Without caching, every script restart or test run incurs this delay.

The "Dynamic" Trap: If you define a @jit function inside a file loaded via importlib (the plugins), cache=True will fail. Always move JIT code to the util/ backend files.

2. **nopython=True** is Non-Negotiable
This forces Numba to compile to pure machine code. If Numba can't compile it (e.g., you tried to use pandas or list.append()), it will throw an error. This prevents "Object Mode" fallbacks which are as slow as standard Python.

3. Handling Multi-Column Outputs
When an indicator returns multiple values (like Volume Profile):

The Backend returns multiple NumPy arrays.

The Wrapper combines them into a pl.DataFrame(...).to_struct().

calculate_polars provides an explicit pl.Struct schema and uses .struct.field("name") to flatten the output.

### 4. Examples

See the following plugins for examples:

- psar [backend](../util/plugins/indicators/helpers/psar_backend.py) [indicator](../util/plugins/indicators/psar.py)
- shannonentropy [backend](../util/plugins/indicators/helpers/shannonentropy_backend.py) [indicator](../util/plugins/indicators/shannonentropy.py)
- marketprofile [backend](../util/plugins/indicators/helpers/marketprofile_backend.py) [indicator](../util/plugins/indicators/marketprofile.py)
- volumeprofile [backend](../util/plugins/indicators/helpers/volumeprofile_backend.py) [indicator](../util/plugins/indicators/volumeprofile.py)