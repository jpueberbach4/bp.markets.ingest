# TA-Lib v0.6.x Installation Guide for WSL2 (Ubuntu)

**VERIFICATION: PENDING!**

This guide provides the specific manual approach for **TA-Lib 0.6.x**. This version is a significant upgrade from 0.4.0 and requires a more modern build process. Use this guide to ensure compatibility with Python 3.10+ and NumPy 2.0+ environments.

## Breaking Changes in 0.6.x
- **Header Location:** Headers are now in a `ta-lib/` subdirectory (e.g., `#include <ta-lib/ta_libc.h>`).
- **Library Naming:** The linking convention has shifted from `_ta_lib` to `ta-lib`.
- **Build System:** Now uses Autotools/CMake; the old `msvc` and `borl` directories have been removed.

---

## 1. System Preparation
Install updated build tools. 0.6.x relies heavily on `libtool` and `automake` for the configuration phase.

```bash
sudo apt update
sudo apt install build-essential wget python3-dev automake libtool -y
```

## 2. Compile the TA-Lib 0.6.4 C-Library
We will fetch the latest stable 0.6.x source from GitHub/SourceForge.

```bash
# Download 0.6.4 Source
wget [https://github.com/TA-Lib/ta-lib/releases/download/v0.6.4/ta-lib-0.6.4-src.tar.gz](https://github.com/TA-Lib/ta-lib/releases/download/v0.6.4/ta-lib-0.6.4-src.tar.gz)
tar -xzf ta-lib-0.6.4-src.tar.gz
cd ta-lib-0.6.4/

# Build and Install
# We use /usr to ensure shared libraries are in the standard path
./configure --prefix=/usr
make
sudo make install
```

## 3. Register Shared Objects (Crucial)
Because 0.6.x changes internal library filenames, you must refresh the dynamic linker cache to prevent ImportError.

```bash
sudo ldconfig
```

## 4. Install the Python Wrapper
Install the version of the wrapper that matches the 0.6.x C-library.

```bash
# Force the 0.6.x wrapper to ensure NumPy 2.0 compatibility
pip install "TA-Lib>=0.6.0"
```

## Developer Validation Suite
Verify that the new namespace and library structure are correctly mapped.

**Check A: Verify Header & Lib Pathing**

Confirm the system recognizes the new ta-lib naming convention:

```bash
ls /usr/include/ta-lib/ta_libc.h
ls /usr/lib/libta-lib.so
```

**Check B: Linkage Check**

```bash
ldd $(python3 -c "import talib; print(talib.__file__)") | grep ta-lib
```

**Note:** If you see libta_lib.so (underscore), you are accidentally still linked to 0.4.0. If you see libta-lib.so (hyphen), you are successfully on 0.6.x.

**Check C: Logic Verification**
Ensure the indicator engine can still process high-precision data from the ingestion pipeline:

```python
import talib
import numpy as np

# Test high-speed EMA calculation
data = np.random.random(100).astype(np.float64)
result = talib.EMA(data, timeperiod=10)

if not np.isnan(result[-1]):
    print("0.6.x VALIDATION SUCCESS")
```

## Troubleshooting 0.6.x

* Compilation Hangs: If make hangs, WSL2 may be low on memory. Increase your WSL2 RAM allocation in .wslconfig to at least 4GB.

* Header Errors: If the Python install fails with "ta_libc.h not found," ensure you used ./configure --prefix=/usr. If you used a custom prefix, you must export: export TA_INCLUDE_PATH=$PREFIX/include export TA_LIBRARY_PATH=$PREFIX/lib
