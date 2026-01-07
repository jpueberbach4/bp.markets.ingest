## IO changes for resampling

We are going to make big changes in these classes. IO will get abstracted

- ResampleIOIndexReaderWriter
  Default positioning commit file handling

- EtlIO (abc.ABC) **
- ResampleIOReader (abc.ABC) **
- ResampleIOWriter (abc.ABC) **
- ResampleIOIndexReaderWriter (abc.ABC) **

- ResampleIOReaderText (Regular handling) - implemented
- ResampleIOWriterText (Regular handling) - implemented
- ResampleIOIndexReaderWriterText (Regular handling) - implemented

- ResampleIOReaderBinary (MemoryMapped)
- ResampleIOWriterBinary (MemoryMapped)
- ResampleIOIndexReaderWriterBinary (16 bytes write, perhaps header)

- ResampleIOFactory - implemented
  To return wither a Text/Binary reader/writer
  get_index_handler(config), get_reader(config), get_writer(config)

**Reason:**

Profiling indicates that 70-80% of execution time is consumed by CSV 
serialization overhead (read_csv/to_csv). Implementing a fixed-length 
binary mode eliminates this bottleneck via a zero-copy architecture. 
By memory-mapping the file and utilizing np.frombuffer, we create a 
direct memory view that bypasses traditional parsing. Furthermore, 
vectorized offset calculations allow for high-performance, crash-safe indexing. 
This approach is significantly more efficient, shifting the workload from 
CPU-intensive string processing to near-native memory speeds.

Goal: support binary reading writing with fallback for CSV
      binary mode will completely eliminate string parsing

Note: have a look at Protocol, runtime_checkable (Duck Typing) **
      it's a new way for "abstraction". might save some time.

**Expected gains:**

At the moment, resampling takes about 90 seconds for 42 symbols. 70 percent of that
time is for read_csv and to_csv. The above will eliminate that full 70 percent almost
completely. So, we drop from 90 seconds to about 30 seconds. Half a minute for
resampling 42 symbols, 10 timeframes, average 15-20 years of 1m data per symbol.
Session-handling logic inclusive.

Furthermore. DuckDB supports a method to directly read from a zero-copy np.frombuffer
array. This is orders of magnitude faster than read_csv. We will gain massively
on DuckDB manipulations as well, thereby massively increasing performance of the
web-interface (for lowest granularities), indicator calculations and builder exports.

I noticed the webinterface having a hard time with 1m and 5m charts. That will become history.

Example:

```python

from typing import Protocol, runtime_checkable

@runtime_checkable
class DataWriter(Protocol):
    def write_at(self, pos: int, data: bytes) -> int:
        ...

class MmapWriter:
    # No explicit inheritance from DataWriter needed!
    def write_at(self, pos: int, data: bytes) -> int:
        return pos + len(data)

def save_data(writer: DataWriter):
    writer.write_at(0, b"OHLCV_DATA")

```

**Update:** Used the ABC method since that is best known to me. Perhaps later use runtime_checkable.