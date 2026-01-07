# Architectural Refactor: High-Performance Binary IO for Resampling, Transform and Aggregate

## Overview

We are transitioning the OHLCV engines from a string-based CSV workflow to a **Zero-Copy Binary Architecture**. 

### The Problem: The "Parsing Tax"

Current profiling indicates that **70-80% of execution time** is consumed by CSV serialization overhead (`read_csv`/`to_csv`). This bottlenecks the system at the CPU, utilizing only about 5% of the machine's actual hardware potential due to constant object creation and string manipulation.

### The Solution: Memory-Mapped Binary Streams

By moving to a fixed-length binary format, we eliminate the parsing bottleneck. Using `mmap` (Memory Mapping) and `np.frombuffer`, we create a direct memory view that treats files on the disk as if they were raw arrays in RAM.

---

## Technical Implementation

### 1. Abstracted IO Layer

The IO logic has been abstracted into a protocol-based hierarchy using Python's `abc.ABC` (Abstract Base Classes). This allows the engine to switch seamlessly between legacy CSV support and the new high-speed Binary format.

* **`EtlIO`**: Base protocol for resource management (context managers).
* **`ResampleIOReader` / `Writer`**: Abstract interfaces for data stream handling.
* **`ResampleIOFactory`**: A singleton factory that detects file formats (e.g., `.bin` vs `.csv`) and returns the appropriate handler.4
* **Others**

| Component | Status | Description |
| :--- | :--- | :--- |
| **Text Handlers** | Implemented | Standard `read_csv` / `to_csv` logic. |
| **Binary Handlers** | Implemented | High-speed `mmap` + `numpy` logic. |
| **Index Handlers** | Implemented | Crash-safe pointers to track processing offsets. |

### 2. The 64-Byte Alignment Strategy

To reach near-native performance, every OHLCV record is padded to exactly **64 bytes**. This is a common C++ optimization (`alignas(64)`) that aligns our data structure with the physical architecture of modern x86_64 CPUs.

* **Hardware Prefetching**: Since 64 bytes is the standard CPU cache-line size, the CPU’s **linear prefetcher** identifies the fixed-stride pattern. It proactively loads the next records into the L1 cache before the Python code even requests them.
* **Eliminating Split-Loads**: This ensures a single record never spans across two cache lines, minimizing memory latency and preventing fetch penalties.
* **SIMD Readiness**: This layout allows NumPy (and future C++ cores) to use vectorized instructions to process multiple bars simultaneously.

---

## Expected Performance Gains

### Processing Throughput

We expect a **3x-5x increase** in resampling speed for our standard workload (42 symbols, 10 timeframes, ~20 years of data).

* **Current (CSV):** ~90 seconds
* **Target (Binary):** ~30 seconds

### Downstream Impact

* **DuckDB Integration**: DuckDB supports reading directly from a zero-copy `np.frombuffer` array. This is orders of magnitude faster than `read_csv`, significantly increasing the performance of the web interface (especially for 1m and 5m charts).

* **Indicator Calculations**: Technical analysis (RSI, MACD) will run on contiguous memory blocks, avoiding the overhead of fragmented Python objects.

---

## Roadmap: Structural Typing (Protocols)

We are exploring a transition from ABCs to **PEP 544 Protocols** (`typing.Protocol`). This allows for "Static Duck Typing," making the code more flexible while maintaining type safety.

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class DataWriter(Protocol):
    def write_at(self, pos: int, data: bytes) -> int:
        ...

class MmapWriter:
    # No explicit inheritance needed to satisfy the DataWriter protocol
    def write_at(self, pos: int, data: bytes) -> int:
        return pos + len(data)

```

This is a further optimization that mainly impacts syntax. Not performance.