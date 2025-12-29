## Project Statistics (Logical SLOC)

As per 29 december 2025

### Project Statistics (Logical SLOC) - ETL

| File Name | Code Lines | Core Responsibility |
| :--- | :---: | :--- |
| `resample.py` | 192 | Pointer-based resampling state machine & "Bugs-Bunnies" logic. |
| `app_config.py` | 112 | Recursive YAML resolving and dataclass mapping. |
| `transform.py` | 102 | Vectorized JSON-to-OHLC conversion using NumPy/Pandas. |
| `run.py` | 91 | Multiprocessing orchestration and pipeline sequencing. |
| `resample_pre_process.py` | 89 | Vectorized session origin and DST-aware batch computations. |
| `download.py` | 84 | HTTP management, rate limiting, and JSON delta merging. |
| `aggregate.py` | 74 | Incremental CSV appending with crash-safe index tracking. |
| `resample_post_process.py` | 56 | Structural fixes and merging intermediate rows into anchor rows. |
| `dst.py` | 33 | DST offset lookups and symbol-to-timezone mapping. |
| `exceptions.py` | 31 | Custom exception hierarchy for ETL traceability. |
| `helper.py` | 18 | MT4 server time math and timezone localization. |
| **Total Project** | **882** | **Logical Source Lines of Code** |

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