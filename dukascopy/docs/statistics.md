## Project Statistics (Logical SLOC)

As per 30 december 2025

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

| File Name     | Logical SLOC | Core Responsibility |
| :--- | :---: | :--- |
| `routes.py`   | 108          | Main API logic: handles request flow, DuckDB SQL generation, and multi-format output.  |
| `app_config.py`| 54           | Configuration engine: maps YAML to nested Dataclasses for type-safe config access.     |
| `helper.py`   | 46           | DSL Parser: decodes path-based URL syntax into structured query parameters.            |
| `run.py`      | 38           | Application entry point: manages server lifecycle and static file mounting.            |
| `version.py`  | 1            | Metadata: defines the current API version string.                                      |
| **Total Project** | **247** | **Logical Source Lines of Code** |

### Project Statistics (Logical SLOC) - Replay

Under development

>Currently about 1750 lines of code.