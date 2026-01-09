## Performance Benchmarks

### Cold Run (Full Update)

> **Hardware:** AMD Ryzen 7 (8C/16T) · 1 TB NVMe SSD · WSL2 (Ubuntu)  
> **Workload:** 20 years of 1-minute OHLC data · **26 symbols** (~520 years total)

| Script        | Time     | Unit/s (unit) | Candles/s (read)    | Data Written | Write Speed |
|---------------|----------|---------|---------------|--------------|-------------|
| `transform.py`| **89 s** | > 2,000 (files) | **1.35 M**   | 7.3 GB       | **82 MB/s** |
| `aggregate.py`| **24 s** | > 2,000 (files) | **5.0 M**   | 6.9 GB       | **260 MB/s** |
| `resample.py`| **122 s** | 0.21 (symbols) | **1 M**   | 2.3 GB       | **19 MB/s** |


**Total pipeline time:** **~3.9 minutes**  

**Throughput (stage average):** **> 1 million candles processed per second** (`Binary mode` some stages reach 3 million candles per second)

**Throughput (pipeline average):** **> 500 thousand candles processed per second** (`Binary mode` doubles that)

>Excellent for commodity hardware.

### Incremental Run (Daily Update)
> **Workload:** 26 symbols × 1 day of new data

| Stage | Time | Throughput | Notes |
|-------|------|------------|-------|
| Download | 0.43s | 60.3 downloads/s | Network limited |
| Transform | 0.02s | **2,439 files/s** | Pure I/O speed |
| Aggregate | 0.01s | **2,122 symbols/s** | Pointer-based append |
| Resample | 0.21s | 118 symbols/s | 10 timeframes cascaded |
| **Total** | **0.67s** | - | **Sub-2-second updates** ⚡ |

>No NVMe but have loads of RAM (>64GB Free)? Put this on TMPFS. It will rock. Safe estimate: 20GB PER 25 symbols (20 years of data). 

> **Reproducible on any modern Ryzen 7 + NVMe setup.**
