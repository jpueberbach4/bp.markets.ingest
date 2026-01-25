## Key Design Principles

- **Binary storage** → CPU cache aligned high performance binary format
- **Incremental processing** → Only new/missing data is handled
- **Pointer tracking** → Enables precise continuation across runs
- **Zero backtracking** → Data is only processed/read once
- **Cascaded resampling** → Minimizes row processing at each timeframe
- **Filesystem-native** → No database required
- **NVMe/SSD Preferred** → High IOPS critical for performance

## Self describing data

Self-describing data for incremental processing: Each row includes its byte position (for crash recovery) and session origin (for proper time grouping), eliminating complex state tracking.

## Fail-Fast

This pipeline follows a **strict fail-fast philosophy**:

- **Any error = Pipeline stops immediately**
- **No silent failures** or partial corruptions  
- **Data integrity > Availability**

**Why?** In financial data, a single corrupted candle can lead to:
- Incorrect technical indicators
- Flawed backtesting results
- Real trading losses

**Implementation:**
- Worker processes: `raise` all exceptions
- Coordinator: Catches and `ABORT`s entire pipeline
- Clear error attribution: "ABORT! Critical error in Transform"

---


## Directory Structure

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