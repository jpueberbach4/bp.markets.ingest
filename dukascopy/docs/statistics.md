## Project Statistics (Logical SLOC)

As per 23 december 2025

### Project Statistics (Logical SLOC) - ETL

| File Name | Code Lines | Core Responsibility |
| :--- | :---: | :--- |
| `resample.py` | 198 | Pointer-based resampling state machine & "Bugs-Bunnies" logic. |
| `transform.py` | 115 | Vectorized JSON-to-OHLC conversion using NumPy/Pandas. |
| `app_config.py` | 112 | Recursive YAML resolving and dataclass mapping. |
| `run.py` | 104 | Multiprocessing orchestration and pipeline sequencing. |
| `helper.py` | 85 | MT4 server time math, session tracking, and path resolution. |
| `download.py` | 81 | HTTP management, rate limiting, and JSON delta merging. |
| `aggregate.py` | 67 | Incremental CSV appending with crash-safe index tracking. |
| `dst.py` | 18 | DST offset lookups and symbol-to-timezone mapping. |
| `exceptions.py` | 14 | Custom exception hierarchy for ETL traceability. |
| **Total Project** | **794** | **Logical Source Lines of Code** |

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

### Project Statistics (Logical SLOC) - HTTP-service

Under development

### Project Statistics (Logical SLOC) - Replay

Under development