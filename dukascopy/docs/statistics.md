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

### Project Statistics (Logical SLOC) - HTTP-service 1.1

| File Name | Code Lines | Core Responsibility |
| :--- | :---: | :--- |
| `helper.py` | 132 | **DSL Parser & Executor**: Decodes path-based URL syntax, resolves data sources, and manages data retrieval with indicator warmup logic. |
| `routes.py` | 89 | **Main API Router**: Defines FastAPI endpoints for OHLCV data and indicator listings; manages request flow and output serialization. |
| `state11.py` | 74 | **State Management**: Manages the `MarketDataCache` using memory-mapped (`mmap`) binary files and NumPy structured arrays for zero-copy access. |
| `parallel.py` | 44 | **Parallel Processor**: Executes technical indicator plugins across data slices using a thread pool for high-performance computation. |
| `run.py` | 33 | **Application Entry Point**: Configures the FastAPI app, manages the lifespan (startup/shutdown), and mounts static documentation files. |
| `plugin.py` | 31 | **Plugin Loader**: Dynamically imports Python modules from the indicators directory and extracts metadata for the registry. |
| `version.py` | 1 | **Metadata**: Defines the `API_VERSION` constant used for routing and documentation. |
| **Total Project** | **404** | **Logical Source Lines of Code** |

Plugins excluded.

### Project Statistics (Logical SLOC) - Replay

Under development

>Currently about 2400 lines of code.