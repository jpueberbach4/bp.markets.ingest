## Project Statistics (Logical SLOC)

As per 20 december 2025

### Project Statistics (Logical SLOC) - ETL

| File Name | Code Lines | Core Responsibility |
| :--- | :---: | :--- |
| `app_config.py` | 172 | Recursive YAML resolving and dataclass mapping. |
| `resample.py` | 156 | Pointer-based resampling state machine & "Bugs-Bunnies" logic. |
| `helper.py` | 118 | MT4 server time math, session tracking, and path resolution. |
| `download.py` | 104 | HTTP management, rate limiting, and JSON delta merging. |
| `run.py` | 92 | Multiprocessing orchestration and pipeline sequencing. |
| `transform.py` | 68 | Vectorized JSON-to-OHLC conversion using NumPy/Pandas. |
| `aggregate.py` | 64 | Incremental CSV appending with crash-safe index tracking. |
| `dst.py` | 34 | DST offset lookups and symbol-to-timezone mapping. |
| **Total Project** | **808** | **Logical Source Lines of Code** |

### Project Statistics (Logical SLOC) - Batch Extraction Utility

| File Name | Code Lines | Core Responsibility |
| :--- | :---: | :--- |
| `args.py` | 114 | CLI parsing, selection validation, and UUID temp-dir generation. |
| `helper.py` | 82 | Regex-based symbol discovery and dataset selection resolving. |
| `run.py` | 74 | Pipeline orchestration, TOS enforcement, and merge/cleanup flow. |
| `extract.py` | 68 | DuckDB SQL generation for time-windowed CSV-to-Parquet extraction. |
| `mt4.py` | 52 | Exporting DuckDB views to MT4-compatible CSV formatting. |
| `app_config.py` | 48 | Lightweight recursive dataclass mapping for the builder config. |
| `merge.py` | 42 | High-speed DuckDB consolidation of partitioned temp files. |
| `tos.py` | 24 | Interactive Terms of Service enforcement and cache-file marking. |
| **Total Project** | **504** | **Logical Source Lines of Code** |