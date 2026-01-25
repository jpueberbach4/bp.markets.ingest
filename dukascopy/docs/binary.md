# Binary OHLCV Format Specification (v0.5 and above)

This document provides a technical specification for the high-performance binary OHLCV (Open, High, Low, Close, Volume) format. It is designed to guide advanced users and developers in implementing compatible I/O engines or debugging data at the byte level.

---

## 1. Design Philosophy
The format is optimized for **zero-copy I/O** and **cache-line alignment**. By using a fixed-width record size that matches standard x86_64 CPU architecture characteristics, the engine achieves near-hardware-limit performance for time-series aggregation.

* **Fixed Record Size:** Exactly 64 bytes.
* **Alignment:** Records are aligned to 64-byte boundaries to prevent split-load penalties and ensure a single record never spans two CPU cache lines.
* **Zero-Copy:** Designed for `mmap` (memory mapping) where the file on disk is mapped directly into the process address space.

---

## 2. Record Structure (64 Bytes)
Each record represents a single OHLCV bar. All multi-byte values are stored in **Little-Endian** format.

| Offset | Length | Name          | Data Type     | Description                                      |
| :---   | :---   | :---          | :---          | :---                                             |
| `0`    | 8      | **Timestamp** | `uint64`      | Unix timestamp in **milliseconds**.              |
| `8`    | 8      | **Open** | `float64`     | Bar opening price.                               |
| `16`   | 8      | **High** | `float64`     | Highest price during the interval.               |
| `24`   | 8      | **Low** | `float64`     | Lowest price during the interval.                |
| `32`   | 8      | **Close** | `float64`     | Bar closing price.                               |
| `40`   | 8      | **Volume** | `float64`     | Total volume traded.                             |
| `48`   | 16     | **Padding** | `uint64` x 2  | Reserved for alignment / future headers.         |

---

## 3. Index File Specification (`.idx`)
The `.idx` file tracks the state of the ETL pipeline to support crash-safe incremental processing.

### Current Version (24 Bytes)
The modern index structure includes date tracking to handle day-boundary logic.

| Offset | Length | Name          | Data Type | Description                                   |
| :---   | :---   | :---          | :---      | :---                                          |
| `0`    | 4      | **last_date** | `int32`   | YYYYMMDD of the last processed record.        |
| `4`    | 4      | **padding** | `uint32`  | Reserved for alignment.                       |
| `8`    | 8      | **in_pos** | `uint64`  | Byte offset in the source file.               |
| `16`   | 8      | **out_pos** | `uint64`  | Byte offset in the destination file.          |

### Legacy Support
The system detects 16-byte index files (containing only `in_pos` and `out_pos`) and automatically migrates them to the 24-byte format upon the first write operation.

---

## 4. Implementation Reference

### NumPy Descriptor
For Python integrations, use the following `dtype` to map the binary data without copying:

```python
import numpy as np

DTYPE = np.dtype([
    ('ts', '<u8'),           # Little-endian uint64
    ('ohlcv', '<f8', (5,)),  # 5x Little-endian float64
    ('padding', '<u8', (2,)) # 2x Little-endian uint64
])
```

### Transactional Integrity
To prevent index corruption during system crashes:

- New index data is written to a .tmp file.
- fsync() is called to ensure data is physically written to the storage media.
- os.replace() is used to perform an atomic swap of the .tmp file with the live .idx file.

### Performance Considerations

1. Vectorization: Because the data is packed and aligned, it can be loaded directly into SIMD registers for high-speed calculation.

2. OS Page Cache: The use of mmap allows the Operating System to manage memory efficiently, swapping pages in from disk only as they are accessed.

3. Concurrency: The format supports multiple concurrent readers. Writers must implement external locking to prevent race conditions.

## 6. Manual Verification (CLI)

For debugging or manual integrity checks, you can use the standard `hexdump` utility on Linux or macOS. 

### Inspecting Records
Since each record is 64 bytes, you can use the `-e` flag to format the output into the specific fields defined in this spec.

```bash
# Display the first 2 records (128 bytes)
# Format: [Timestamp] [Open] [High] [Low] [Close] [Volume]
hexdump -n 128 -e '1/8 "TS: %u | " 5/8 " %f " 2/8 " (pad) " "\n"' data.bin
```

### Understanding the Hex Output

If you use a raw hex dump (hexdump -C), you can verify the alignment and padding visually:

```sh
hexdump -C -n 128 data.bin

```
What to look for:

1. Little-Endian Timestamps: The first 8 bytes (Offset 0x00) will have the least significant bytes first.

2. Double Precision Floats: Offsets 0x08 through 0x28 contain the OHLCV data. Values like 1.08014 will look like a sequence of non-zero hex bytes.

3. The Null Gap: Offsets 0x30 through 0x3F (the last 16 bytes of the block) should be consistent padding (usually all zeros 00).


## 7. Troubleshooting

### Troubleshooting

| Symptom | Probable Cause | Resolution |
| :--- | :--- | :--- |
| **BufferError** | Python view is still active | Clear all NumPy views (`del view`) before closing `mmap`. |
| **Bus Error / SIGBUS** | File truncated while mapped | Ensure writers don't truncate files currently being read. |
| **Negative Prices** | Logic Error | Check endianness; ensure you are reading as `<f8` (Little Endian). |
| **Offset Drift** | Incorrect Record Size | Ensure you are seeking in multiples of 64. |


### Python dump example

```python
import numpy as np
import pandas as pd
from pathlib import Path

# Match your binary.py definition
DTYPE = np.dtype([
    ('ts', '<u8'),           # Timestamp uint64
    ('ohlcv', '<f8', (5,)),  # OHLCV float64
    ('padding', '<u8', (2,)) # Padding
])

def dump_binary_file(filepath: str, num_records: int = 10):
    path = Path(filepath)
    if not path.exists():
        print(f"File not found: {filepath}")
        return

    # Map the file and read records
    data = np.fromfile(path, dtype=DTYPE)
    
    # Convert to DataFrame for readable output
    df = pd.DataFrame(
        data['ohlcv'],
        columns=['open', 'high', 'low', 'close', 'volume'],
        index=pd.to_datetime(data['ts'], unit='ms')
    )
    
    print(f"--- Top {num_records} records of {path.name} ---")
    print(df.head(num_records))
    print(f"\n--- Bottom {num_records} records of {path.name} ---")
    print(df.tail(num_records))
    print(f"\nTotal Records: {len(data)}")

# Usage
dump_binary_file("data/aggregate/1m/EUR-USD.bin")
```

### Python zero-copy view example

```python
import numpy as np
import mmap
from pathlib import Path

# 1. Define the specification-compliant DTYPE
# <u8  = Little-endian uint64 (Timestamp)
# <f8  = Little-endian float64 (OHLCV)
DTYPE = np.dtype([
    ('ts', '<u8'),           
    ('ohlcv', '<f8', (5,)),  
    ('padding', '<u8', (2,)) 
])

def load_ohlcv_binary(filepath: str):
    path = Path(filepath)
    
    # 2. Open file handle
    f = open(path, "rb")
    
    try:
        # 3. Create Memory Map (Zero-copy)
        # length=0 maps the whole file
        mm = mmap.mmap(f.fileno(), length=0, access=mmap.ACCESS_READ)
        
        # 4. Create the NumPy view from the buffer
        # This does not copy the data into RAM
        data = np.frombuffer(mm, dtype=DTYPE)
        
        # Accessing data is now vectorized and fast
        print(f"Loaded {len(data)} records.")
        print(f"First timestamp: {data['ts'][0]}")
        print(f"First Close: {data['ohlcv'][0, 3]}")
        
        return data, mm, f
        
    except Exception as e:
        f.close()
        raise e

# Usage
# data_view, mm_handle, f_handle = load_ohlcv_binary("EURUSD_1m.bin")

# IMPORTANT: To close safely, you must delete the numpy view first
# del data_view
# mm_handle.close()
# f_handle.close()
```