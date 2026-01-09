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

PS. This is no longer a "toy-project". These kind of optimizations are typically seen in HFT environments.

## First results on performance (unoptimized)

* **EUR-USD, CSV-mode, 20 years of data, 10 timeframes, no session rules**

```sh
Deleting data/*...
Rebuilding...
Running Dukascopy ETL pipeline (16 processes)
Using lockfile data/locks/run.lock
Step: Download...
100%|████████████████████████████████████████████| 1/1 [00:00<00:00,  4.53downloads/s]
Step: Transform...
100%|████████████████████████████████████████████| 7677/7677 [00:06<00:00, 1114.18files/s]
Step: Aggregate...
100%|████████████████████████████████████████████| 1/1 [00:02<00:00,  2.76s/symbols]
Step: Resample...
100%|████████████████████████████████████████████| 1/1 [00:28<00:00, 28.14s/symbols]

ETL pipeline complete!
Total runtime: 38.42 seconds (0.64 minutes)
Done.
```


* **EUR-USD, BINARY-mode, 20 years of data, 10 timeframes, no session rules**

```sh
jpueberb@LAPTOP-0LK1UE8L:~/repos2/bp.markets.ingest/dukascopy$ ./rebuild-full.sh
Deleting data/*...
Rebuilding...
Running Dukascopy ETL pipeline (16 processes)
Using lockfile data/locks/run.lock
Step: Download...
100%|████████████████████████████████████████████| 1/1 [00:00<00:00,  3.37downloads/s]
Step: Transform...
100%|████████████████████████████████████████████| 7677/7677 [00:03<00:00, 2239.16files/s]
Step: Aggregate...
100%|████████████████████████████████████████████| 1/1 [00:03<00:00,  3.05s/symbols]
Step: Resample...
100%|████████████████████████████████████████████| 1/1 [00:02<00:00,  2.52s/symbols]

ETL pipeline complete!
Total runtime: 9.69 seconds (0.16 minutes)
Done.
```

* **EUR-USD, BINARY-mode, verification of 15m data:**

```sh
Total Records: 1440
--- Top 10 records of EUR-USD.bin ---
                        open     high      low    close  volume
2005-01-03 00:00:00  1.35464  1.35560  1.35464  1.35548  7598.0
2005-01-03 00:15:00  1.35534  1.35619  1.35486  1.35610  6961.5
2005-01-03 00:30:00  1.35583  1.35612  1.35456  1.35537  7477.4
2005-01-03 00:45:00  1.35555  1.35620  1.35491  1.35593  8176.8
2005-01-03 01:00:00  1.35573  1.35676  1.35540  1.35652  8413.6
2005-01-03 01:15:00  1.35670  1.35704  1.35616  1.35630  7331.3
2005-01-03 01:30:00  1.35604  1.35685  1.35596  1.35660  7309.3
2005-01-03 01:45:00  1.35656  1.35771  1.35638  1.35761  7878.8
2005-01-03 02:00:00  1.35772  1.35777  1.35627  1.35662  7683.9
2005-01-03 02:15:00  1.35629  1.35641  1.35568  1.35621  7121.0

--- Bottom 10 records of EUR-USD.bin ---
                        open     high      low    close   volume
2026-01-07 17:45:00  1.16953  1.16956  1.16831  1.16901  1943.41
2026-01-07 18:00:00  1.16900  1.16931  1.16823  1.16827  1613.25
2026-01-07 18:15:00  1.16829  1.16879  1.16822  1.16854   989.43
2026-01-07 18:30:00  1.16856  1.16906  1.16844  1.16892  1991.03
2026-01-07 18:45:00  1.16892  1.16893  1.16841  1.16893  1338.77
2026-01-07 19:00:00  1.16892  1.16948  1.16873  1.16880  1301.47
2026-01-07 19:15:00  1.16879  1.16900  1.16862  1.16895  1381.92
2026-01-07 19:30:00  1.16895  1.16911  1.16877  1.16903  1674.40
2026-01-07 19:45:00  1.16904  1.16916  1.16861  1.16879  1576.97
2026-01-07 20:00:00  1.16880  1.16897  1.16856  1.16890   781.85

Total Records: 524096
```

Correct.

** Can't wait to see DuckDB performance on this **

I am still optimizing transform and aggregate, but these two saturate the NVMe drive. Don't know if can make faster if hardware says no.

## Key Takeaways

| Operation | CSV Mode | Binary Mode | Speedup |
| :--- | :--- | :--- | :--- |
| **Transform** | 6.00s | 3.00s | 2.0x faster |
| **Aggregate** | 2.76s | 3.05s | (Slightly slower - optimizing) |
| **Resample** | 28.14s | 2.52s | **11.2x FASTER!** 🎉 |
| --- | --- | --- | --- |
| **TOTAL** | **38.42s** | **9.69s** | **4.0x FASTER OVERALL** |

Total bars: 7,861,440

**Actual throughput: ~810,000 bars/second**

That's astonishing performance for a "python script". On a 2023 laptop.


42 symbols, CSV-mode:

```sh
Deleting data/*...
Rebuilding...
Running Dukascopy ETL pipeline (16 processes)
Using lockfile data/locks/run.lock
Step: Download...
100%|██████████████████████████████████████| 42/42 [00:03<00:00, 12.38downloads/s]
Step: Transform...
100%|██████████████████████████████████████| 322434/322434 [02:12<00:00, 2426.63files/s]
Step: Aggregate...
100%|██████████████████████████████████████| 42/42 [00:39<00:00,  1.07symbols/s]
Step: Resample...
100%|██████████████████████████████████████| 42/42 [01:49<00:00,  2.62s/symbols]

ETL pipeline complete!
Total runtime: 297.26 seconds (4.95 minutes)
Done.
```

42 symbols, BINARY-mode:

```sh
Deleting data/*...
Rebuilding...
Running Dukascopy ETL pipeline (16 processes)
Using lockfile data/locks/run.lock
Step: Download...
100%|███████████████████████████████████████| 42/42 [00:03<00:00, 12.54downloads/s]
Step: Transform...
100%|███████████████████████████████████████| 322476/322476 [00:54<00:00, 5955.18files/s]
Step: Aggregate...
100%|███████████████████████████████████████| 42/42 [00:34<00:00,  1.22symbols/s]
Step: Resample...
100%|███████████████████████████████████████| 42/42 [00:23<00:00,  1.81symbols/s]

ETL pipeline complete!
Total runtime: 126.00 seconds (2.10 minutes)
Done.
```

2 minutes now for 42 symbols with an average history of 15 years of 1m candles per symbol. with custom timeframes, session handling, all-in.

Transform is now almost maximum performance - last optimizations was microseconds stuff, but on 300k files these add up
Aggregate completely saturates the NVMe drive.
Resample is optimal.

I will finalize this binary implementation:

- Adding support for binary files to builder component
- Adding support for binary files to webservice component
- Adding MAGIC bytes and version info into the binary file's header
- Few QA passes