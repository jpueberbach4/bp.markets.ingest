## Project Statistics (Logical SLOC)

As per 9 january 2026

### Project Statistics (Logical SLOC) - ETL

| File Name | Code Lines | Core Responsibility |
| :--- | :---: | :--- |
| `resample.py` | 196 | Pointer-based resampling state machine |
| `binary.py` | 158 | High-performance binary I/O with mmap and NumPy memory views. |
| `text.py` | 142 | Text-based incremental OHLCV file I/O and CSV aggregation. |
| `app_config.py` | 114 | Recursive YAML resolving and dataclass mapping. |
| `transform.py` | 114 | Vectorized JSON-to-OHLC conversion using NumPy/Pandas. |
| `run.py` | 108 | Multiprocessing orchestration and pipeline sequencing. |
| `resample_pre_process.py` | 92 | Vectorized session origin and DST-aware batch computations. |
| `download.py` | 89 | HTTP management, rate limiting, and JSON delta merging. |
| `aggregate.py` | 82 | Incremental CSV appending with crash-safe index tracking. |
| `resample_post_process.py` | 58 | Structural fixes and merging intermediate rows into anchor rows. |
| `protocols.py` | 44 | Abstract base interfaces (protocols) for I/O consistency. |
| `dst.py` | 38 | DST offset lookups and symbol-to-timezone mapping. |
| `exceptions.py` | 36 | Custom exception hierarchy for ETL traceability. |
| `helper.py` | 24 | MT4 server time math and timezone localization. |
| **Total Project** | **1,295** | **Logical Source Lines of Code** |

### Project Statistics (Logical SLOC) - Batch Extraction Utility

| File Name | Code Lines | Core Responsibility |
| :--- | :---: | :--- |
| `adjust.py` | 218 | Panama rollover calendar fetching, caching, and DuckDB price adjustment. |
| `run.py` | 121 | Pipeline orchestration, TOS enforcement, and merge/cleanup flow. |
| `helper.py` | 93 | Regex-based symbol discovery and dataset selection resolving. |
| `extract.py` | 80 | DuckDB SQL generation for time-windowed CSV-to-Parquet extraction. |
| `app_config.py` | 48 | Lightweight recursive dataclass mapping for the builder config. |
| `args.py` | 34 | CLI parsing, selection validation, and UUID temp-dir generation. |
| `merge.py` | 31 | High-speed DuckDB consolidation of partitioned temp files. |
| `mt4.py` | 27 | Exporting DuckDB views to MT4-compatible CSV formatting. |
| `tos.py` | 18 | Interactive Terms of Service enforcement and cache-file marking. |
| **Total Project** | **670** | **Logical Source Lines of Code** |

### Project Statistics (Logical SLOC) - HTTP-service

| File Name | Code Lines | Core Responsibility |
| :--- | :---: | :--- |
| `helper.py` | 248 | DSL Parser: Decodes path-based URL syntax, resolves data sources, and generates DuckDB SQL. |
| `routes.py` | 134 | Main API logic: Handles request flow, versioning, and multi-format output generation. |
| `state.py` | 64 | State management: Manages DuckDB connections and memory-mapped binary file views. |
| `run.py` | 51 | Application entry point: Manages FastAPI/Uvicorn lifecycle and static file mounting. |
| `app_config.py` | 46 | Configuration engine: Maps YAML to nested Dataclasses for type-safe config access. |
| `plugin.py` | 23 | Plugin loader: Dynamically imports and registers indicator plugins from the filesystem. |
| `version.py` | 1 | Metadata: Defines the current API version string. |
| **Total Project** | **567** | **Logical Source Lines of Code** |

Plugins excluded.

### Project Statistics (Logical SLOC) - Replay

Under development

>Currently about 2500 lines of code.