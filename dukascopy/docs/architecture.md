## Key Design Principles

- **CSV-based storage** → Simplifies resume logic via file offsets
- **Incremental processing** → Only new/missing data is handled
- **Pointer tracking** → Enables precise continuation across runs
- **Zero backtracking** → Data is only processed/read once
- **Cascaded resampling** → Minimizes row processing at each timeframe
- **Filesystem-native** → No database required
- **NVMe/SSD Preferred** → High IOPS critical for performance

---

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

## Output schema

All intermediate and final outputs use the same standardized OHLCV CSV format.

```sh
time, open, high, low, close, volume
2025-11-26 00:00:00,1.15648,1.16021,1.1547,1.16017,108027.31
2025-11-27 00:00:00,1.16018,1.16132,1.15763,1.15996,51613.66
2025-11-28 00:00:00,1.15995,1.16075,1.1555,1.15973,177674.44
2025-11-30 00:00:00,1.1594,1.16078,1.15912,1.1601,3303.65
2025-12-01 00:00:00,1.16011,1.16522,1.15893,1.16066,93031.96
2025-12-02 00:00:00,1.16069,1.1629,1.1591,1.1628,74084.42
2025-12-03 00:00:00,1.1628,1.16775,1.16277,1.16661,95673.2
2025-12-04 00:00:00,1.16662,1.16819,1.16409,1.16431,79510.51
2025-12-05 00:00:00,1.16433,1.16717,1.16415,1.16467,37127.59
```

**Types:**

| Column | Type (Implied) | Type (Explicit) |
| :--- | :--- | :--- |
| time | Timestamp (String) | TIMESTAMP or DATETIME |
| open, high, low, close | Double/Float | DOUBLE |
| volume | Double/Float | DOUBLE |

**Note on Precision:**
- Timestamps are (by default) in UTC and follow YYYY-MM-DD HH:MM:SS (use ```time_shift_ms``` to shift to eg GMT+2)
- Price values are rounded to configurable decimal places (default: 8)
- Volume represents the total trading activity for the period

---

## Directory Structure

```sh

project_root/
├── symbols.txt                                # List of trading symbols
├── etl                                        # ETL pipeline code
├── builder                                    # Builder code
├── build-csv.sh                               # CSV builder script
├── build-parquet.sh                           # Parquet builder script
├── run.sh                                     # Runs ETL pipeline
├── rebuild-full.sh                            # Rebuild from scratch
├── rebuild-weekly.sh                          # Redownload data from last week and rebuild (safety-net regarding backfilling)
├── cache/                                     # Cached historical JSON data
│   └── YYYY/
│       └── MM/
│           └── SYMBOL_YYYYMMDD.json           # Delta file
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
└── README.md                                  # Project documentation

```