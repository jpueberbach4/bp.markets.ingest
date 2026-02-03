# 🏗️ Technical Architecture: High-Performance Data Ingest & Analytics

This project is a high-throughput, local-first financial data engine designed to bridge the gap between raw 1m data ingestion and ML-ready feature engineering. It currently serves a decent community and focusses on hardware-limit performance.

## 1. The Core Engine: "Mechanical Sympathy" Architecture
The system is built on the principle of **Mechanical Sympathy**—designing software that works in harmony with modern CPU and storage architecture.

* **Memory-Mapped I/O (`mmap`):** Bypasses standard file-system overhead by mapping binary datasets directly into the process address space.
* **64-Byte Cache-Line Alignment:** Records are structured in 64-byte blocks to match x86_64 cache lines, preventing split-load penalties and maximizing L1/L2 cache efficiency.
* **Zero-Copy Operations:** Data is read as NumPy views rather than being copied into memory, enabling throughput of **38M+ records/sec** on consumer-grade NVMe hardware using a tuned batch-size, in this case the optimal size seems to be 500K.



---

## 2. Hybrid Indicator Engine: Rust-Powered Analytics
To resolve the bottleneck of Python-based technical analysis, the engine utilizes a **Hybrid Execution Model**.

| Engine | Execution Type | Use Case | Performance Delta |
| :--- | :--- | :--- | :--- |
| **Polars (Rust)** | Vectorized/Lazy | Standard Indicators (SMA, RSI, etc.) | **12.5x Speedup** |
| **Pandas** | Eager/Concurrent | Custom UDFs and Legacy logic | Baseline |

### Key Optimization: Lazy Expression Trees
By leveraging Polars' lazy API, the engine optimizes the computation graph for up to 3500-on 100K data-slices-concurrent indicators. The  **Price-only API** stays around **13ms per 500k records**.



---

## 3. Reliability & Data Integrity
Managing **15+ years of historical data** across 42 symbols requires a rigorous validation framework.

* **99.96% Success Rate:** Validated against 321,888 files with automated OHLC consistency checks.
* **Fault-Tolerant ETL:** The pipeline identifies and isolates "Historical Anomalies" (e.g., 2008 Financial Crisis, 2014 Oil Volatility) without halting the global ingestion process.
* **Continuous Validation:** Automated audits ensure that "Founder-speed" development never compromises "Enterprise-grade" data stability.



---

## 4. Roadmap: Distributed & Decoupled Architecture (v0.6.8)
The next evolution of the platform focuses on **Horizontal Scalability** and **Resilience**.

* **FLIGHT/DOWNLOAD Decoupling:** Separating the ingestion layer from the processing engine. Modularity.
* **Kubernetes-Ready ETL:** Transitioning from a single-machine tool to a containerized, distributed infrastructure for larger-scale workloads.
* **High-Speed Communication Layer:** Implementing an IPC (Inter-Process Communication) layer for data streaming between ingestion nodes and ML inference engines.

---

## 5. Performance Benchmarks
* **Throughput:** 2.5 GB/s (Warmed up, Price-only API). Batchsize: 500K.
* **Concurrency:** 16-Core optimized threading achieving **12x factor** over single-threaded baseline.
* **ML Integration:** This is one of the core targets why this engine exists.

---

*Verified Performance on NVMe Laptop Hardware (v0.6.7-beta)*


## 6. Directory Structure

```sh
project_root/
├── symbols.txt                                # List of trading symbols
├── api                                        # API code
├── builder                                    # Builder code
├── build-csv.sh                               # CSV builder script
├── build-parquet.sh                           # Parquet builder script
├── cache/                                     # Cached historical JSON data
│   └── YYYY/
│       └── MM/
│           └── SYMBOL_YYYYMMDD.json           # Delta file
├── config                                     # Default configuration directory
├── config.dukascopy-mt4.yaml                  # Dukascopy example configuration
├── config.yaml                                # Default configuration file
├── data/
│   ├── aggregate/1m/                          # Aggregated CSV output
│   │   ├── index/                             # Pointer/index files for incremental loading
│   │   │   └── SYMBOL.idx
│   │   └── SYMBOL.csv                         # Final aggregated CSV per symbol
│   ├──locks/                                  # File-based locks for concurrency control
│   │   ├── run.lock                           # Protection against simultaneous run.py's  
│   │   └── SYMBOL_YYYYMMDD.lck
│   ├── resample/5m/                           # Resampled CSV output (5m, 15m, 30m, 1h, ...)
│   │   ├── index/                             # Pointer/index files for incremental loading
│   │   │   └── SYMBOL_1m.idx
│   │   └── SYMBOL.csv                         # Final resampled CSV per symbol
│   ├──temp/                                   # Live/current day data (JSON, CSV)
│   │   ├── SYMBOL_YYYYMMDD.json
│   │   └── SYMBOL_YYYYMMDD.csv
│   └── transform/1m/                          # Transformed CSV output
│       └── YYYY/
│           └── MM/
│               └── SYMBOL_YYYYMMDD.csv
├── etl                                        # ETL pipeline code
├── run.sh                                     # Runs ETL pipeline
├── rebuild-aggregate.sh                       # Rebuild aggregated files and resampled files
├── rebuild-full.sh                            # Rebuild from scratch
├── rebuild-resample.sh                        # Rebuild resampled files only
├── rebuild-weekly.sh                          # Redownload data from last week and rebuild (safety-net regarding backfilling)
├── setup-dukascopy.sh                         # Dukascopy initialization script
├── symbols.txt                                # Default symbols file
├── util                                       # Utility code
└── README.md                                  # Project documentation

```

Always consult the documentation.