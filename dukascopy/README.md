# Dukascopy Data Pipeline

## Introduction

Python toolkit to download, transform, load, and resample 1-minute OHLC data from Dukascopy into efficient, appendable CSV files.

**Process 520 years of market data in 5 minutes. Updates all symbols in about 2 seconds.**

High-performance Python pipeline for Dukascopy OHLC data with:

- ⚡ **Sub 2-second incremental updates** (26 symbols × 10 timeframes)
- 🔄 **Crash-resistant** offset-based checkpoints
- 📊 **Cascading resampling** (1m → 5m → ... → 1Y)
- 🚀 **1M+ candles/second** throughput
- 💾 **Zero-database** architecture

Converts Dukascopy's delta-encoded format into appendable CSV files with offset-based resumption and incremental updates.

---

## What Is This Tool Used For?

>This tool builds a high-quality historical OHLCV dataset and maintains it automatically with efficient incremental updates. 
>
>Its crash-resilient architecture is engineered to avoid full dataset rebuilds whenever possible.

Historical market data can be leveraged in multiple ways to enhance analysis, decision-making, and trading performance:

- **Backtesting** → Evaluate and refine trading strategies by simulating them on past market conditions. This helps determine whether a strategy is robust, profitable, and resilient across different market environments.

- **Technical Analysis** → Use historical charts to identify trends, chart patterns, support- and resistance levels. You can also perform correlation studies to compare long-term relationships between currency pairs or other assets.

- **Seasonal Analysis** → Detect recurring market behaviors or unusual pricing patterns that tend to appear during specific months, weeks, or seasons.

- **Volatility Assessment** → Analyze historical volatility to adjust risk parameters, optimize position sizing, and set more accurate stop-loss levels.

- **Computational Intelligence** → Build machine-learning or statistical models trained on historical price data to forecast potential market movements.

- **Economic Event Impact** → Study how past economic releases, geopolitical events, and news shocks influenced currency pairs — helping you prepare for similar situations in the future.

---

## Key Design Principles

- **CSV-based storage** → Simplifies resume logic via file offsets
- **Incremental processing** → Only new/missing data is handled
- **Pointer tracking** → Enables precise continuation across runs
- **Cascaded resampling** → Minimizes row processing at each timeframe
- **Filesystem-native** → No database required
- **NVMe/SSD Preferred** → High IOPS critical for performance

---

## Quick start

Make sure python version is 3.8+. 

```sh
python3 --version
```

For this Dukascopy Data Pipeline project, the Python dependencies that need to be installed via pip are:

| Package    | Version    | Purpose                                                                      |
|----------- |----------- |---------------------------------------------------------------------------- |
| `pandas`   | >=2.0.3    | CSV I/O, data manipulation, aggregation, and incremental loading           |
| `numpy`    | >=1.24.4   | Vectorized numeric computations, cumulative OHLC calculations              |
| `orjson`   | >=3.10.15  | Fast JSON parsing for delta-encoded files                                   |
| `requests` | >=2.22.0   | Download Dukascopy JSON via HTTP                                            |
| `tqdm`     | >=4.67.1   | Progress bars for download, transform, and aggregate loops                  |
| `filelock` | >=3.16.1   | File-based locks to prevent race conditions in parallel processing          |


Install with:

```sh
pip install -r requirements.txt
```

---

**Permission Note(!):**

These scripts read from and write to both the data directory and the cache directory. If your system uses strict permission settings, ensure that the ./data directory is created in advance (the cache directory is already provided).

```sh
mkdir -p ./data
chown -R $USER:$USER ./data ./cache
chmod u+rwx ./data ./cache
```
---

Set START_DATE in run.py to (for initial cold run):

```python
START_DATE = "2005-01-01"
```

Next, run the pipeline with:

```sh
./run.sh
```

When completed, update START_DATE in run.py to:

```python
START_DATE = None
```

This will enable incremental updates. Make sure you run it at least once a week to not miss out on any data.

Optionally, configure a cronjob for periodical execution: 

```sh
crontab -e
```

Add the following line, adjust path accordingly:

```sh
* * * * * cd /home/repos/bp.markets.ingest/dukascopy && ./run.sh
```

---

## Symbols configuration

This project includes a symbols.txt file, which is a single-column CSV containing symbol identifiers.
If you wish to override this default list of symbols

```sh
cp symbols.txt symbols.user.txt
```

Next edit symbols.user.txt to include your symbols of interest (symbols.user.txt is in .gitignore). 

---

All symbols supported by the Dukascopy API are available, with no restrictions. 

Please see here for a complete symbol list:

[Dukascopy historical download](https://www.dukascopy.com/swiss/english/marketwatch/historical/)

**Example**. Suppose we want to add **EUR/MXN** to our setup. We visit the link above and copy the symbol name exactly as shown in the screenshot below.

![Dukascopy download screenshot](images/dukascopysymbols.png)

Add the symbol as a new row in symbols.user.txt. Next, set 

```python
START_DATE = "2005-01-01"
```

in run.py and run the pipeline using:

```sh
./run.sh
```

The pipeline will begin downloading the symbol's historical data (this may take some time) and then execute the remaining steps.

Once the process is complete, set 

```python
START_DATE=None
```

in run.py. The new symbol is now added and will be updated automatically during each incremental run.

---

## Pipeline (Run Sequentially)

| Script | Purpose |
|-------|--------|
| `download.py` | Downloads missing Delta files; **always updates today** |
| `transform.py` | Converts Delta → full CSV; **always processes today** |
| `aggregate.py` | Merges new rows from `data/temp` and `data/transform` into `aggregate/` using **pointer files** |
| `resample.py` | Cascaded resampling: 1m → 5m → 15m → ... → 1M using **resample pointers** |

OR

Run all via:

```sh
./run.sh
```

---

## Performance Benchmarks

### Cold Run (Full Update)

> **Hardware:** AMD Ryzen 7 (8C/16T) · 1 TB NVMe SSD · WSL2 (Ubuntu)  
> **Workload:** 20 years of 1-minute OHLC data · **26 symbols** (~520 years total)

| Script        | Time     | Unit/s (unit) | Candles/s (read)    | Data Written | Write Speed |
|---------------|----------|---------|---------------|--------------|-------------|
| `transform.py`| **89 s** | > 2,000 (files) | **1.35 M**   | 7.3 GB       | **82 MB/s** |
| `aggregate.py`| **37 s** | > 2,000 (files) | **3.26 M**   | 6.7 GB       | **170 MB/s** |
| `resample.py`| **122 s** | 0.21 (symbols) | **1 M**   | 2.3 GB       | **19 MB/s** |


**Total pipeline time:** **~4.2 minutes**  
**Throughput:** **> 1 million candles processed per second (78 million per minute)**

### Incremental Run (Daily Update)
> **Workload:** 26 symbols × 1 day of new data

| Stage | Time | Throughput | Notes |
|-------|------|------------|-------|
| Download | 0.43s | 60.3 downloads/s | Network limited |
| Transform | 0.02s | **2,439 files/s** | Pure I/O speed |
| Aggregate | 0.01s | **2,122 symbols/s** | Pointer-based append |
| Resample | 0.21s | 118 symbols/s | 10 timeframes cascaded |
| **Total** | **0.67s** | - | **Sub-2-second updates** ⚡ |

This enables:
- ⚡ Real-time trading workflows (run every minute)
- 🔄 Fresh backtesting data in under 2 seconds
- 📊 Near-zero latency for strategy development


Full 20 year run on 26 symbols:
![Full run (20 years, 26 symbols)](images/fullrun.png)
After that, incremental updates on 26 symbols:
![Incremental run (26 symbols)](images/incrementalrun.png)

⚠️  Performance scales linearly with symbol count and dataset size; results may differ on HDDs or older SSDs. 

### No NVMe but have loads of RAM (>64GB Free)?

>Put this on TMPFS. It will rock. 
 Safe estimate: 20GB PER 25 symbols (20 years of data). 

---

### Key Takeaways

- **I/O bound, not CPU bound** for aggregate and transform → NVMe is the hero.
- **CPU bound, not I/O bound** for resample → CPU is the hero (will be fixed using vectorizing).
- **I/O (network) bound** for download → Connection is the hero.
- **> 2,000 files/sec** → Proves efficient file handling.
- **> 80 MB/s sustained write** → Excellent for CSV appends.
- **WSL2 performs near-native** on NVMe (minimal overhead).

> **Reproducible on any modern Ryzen 7 + NVMe setup.**

---

## 🚨 Fail-Fast Design Principle

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

### What to Do When Pipeline Fails

1. **Check the error message**: "ABORT! Critical error in Transform"
2. **Investigate the root cause**: Check logs, data files
3. **Fix the issue**: Corrupted file? Network issue?
4. **Restart pipeline**: It will resume from last good state

Example recovery:
```bash
# Pipeline fails with "JSON parse error"
rm cache/2024/03/EURUSD_20240315.json  # Remove corrupted file
./run.sh  # Restart - will redownload & continue
```

---

## Directory Structure

```sh

project_root/
├── symbols.txt                                # List of trading symbols
├── download.py                                # Download Dukascopy JSON data
├── transform.py                               # Transform JSON -> OHLC CSV
├── aggregate.py                               # Aggregate CSVs per symbol
├── resample.py                                # Cascaded resampling to other timeframes
├── run.py                                     # Runs all stages of the pipeline within a single pool, in correct order
├── run.sh                                     # Runs run.py
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

---

## Troubleshooting

### Stale Locks
If pipeline was interrupted (laptop sleep, SIGKILL), remove stale locks:
```bash
rm -rf data/locks/*.lck
```

### Rebuild from scratch?

Set START_DATE in run.py to 2005-01-01

```bash
rm -rf ./data/*
./run.sh
```

Set START_DATE in run.py to None (enables incremental mode)

### Performance Issues
- **Slow first run?** Normal - processing 20 years of data takes time
- **Slow incremental?** Check if NVMe/SSD. HDDs will be 10-50x slower
- **High CPU?** Reduce `NUM_PROCESSES` in scripts
- **Out of memory?** Reduce `BATCH_SIZE` in resample.py (default: 500K)

---

## Notes and Future Work

>HTTP API for OHLC retrieval

>Cascaded indicator engine

>YAML-based configuration

>DuckDB analytical layer

---

## DuckDB (Experimental/Advanced users)

You can try the following:

```python
# db.py - Instant analytical warehouse on top of your CSVs
import duckdb
from pathlib import Path

con = duckdb.connect(database='dukascopy.db', read_only=False)

# Auto-discover ALL your resampled CSVs magically
data_dir = Path("data/resample")
timeframes = [p.name for p in data_dir.iterdir() if p.is_dir() and p.name != "1m"]

for tf in timeframes + ["1m"]:
    pattern = f"data/resample/{tf}/*.csv" if tf != "1m" else "data/aggregate/1m/*.csv"
    con.execute(f"""
        CREATE OR REPLACE VIEW ohlcv_{tf} AS
        SELECT 
            substr(filename, position('//' IN filename) + 2) AS symbol,
            TRY_STRPTIME(timestamp, '%Y-%m-%d %H:%M:%S') AS ts,
            open, high, low, close, volume
        FROM read_csv('{pattern}', filename=true, columns={{'timestamp':'VARCHAR','open':'DOUBLE','high':'DOUBLE','low':'DOUBLE','close':'DOUBLE','volume':'DOUBLE'}})
    """)

# Master union view — query ALL timeframes like one table
con.execute("""
    CREATE OR REPLACE VIEW ohlcv AS
    SELECT * FROM ohlcv_1m
    UNION ALL BY NAME
    SELECT * FROM ohlcv_5m
    UNION ALL BY NAME
    SELECT * FROM ohlcv_15m
    -- add the rest automatically if you want
""")

print("🚀 DuckDB warehouse ready — query with con.sql('SELECT ...')")
```

---

## BUG Tracking

| ID | File | Description | Severity | Status |
|--------|------|-------------|----------|--------|
| 001 | transform.py | Dukascopy filters out rows with zero volume in its historical data and charting tools to focus on periods with actual trading activity, as zero volume indicates a lack of transactions at that price level or time period. This is a standard practice to clean up data for analysis and trading, as a zero-volume row would not provide meaningful insights into market behavior. Today's data contains 0 volume candles, historic data does not. Leading to pointer file imbalance during rollover. Solution is to filter out 0 volume candles in today's CSV. | SEVERE | SOLVED |
| 002 | aggregate.py | When f_out write is interrupted (SIGTERM, OOM, ...), the idx file may not get written and/or aggregate file may get partially updated, leading to invalid data in aggregate file. Solution is similar to resample.py solution. But. We need to keep a third record since there is a many-to-one relationship between transform.py and aggregate.py. We will need to store the input date as well to the idx file. So idx file will contain date, input_position, output_position. This will solve it. Expect it to be solved soon. This will make the complete pipeline crash-safe. **NOTE** YOU WILL NEED TO REINDEX. INTERMEDIATE STRUCTURE CHANGED. FOLLOW REBUILD FROM SCRATCH STEP.| HIGH | SOLVED |

---

## License

This software is licensed under the MIT License.

Copyright JP Ueberbach, 2025

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Dukascopy Ready](https://img.shields.io/badge/Dukascopy-Ready-006400?style=flat&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJ3aGl0ZSI+PHBhdGggZD0iTTEyIDJDNi40OCAyIDIgNi40OCAyIDEyczQuNDggMTAgMTAgMTAgMTAtNC40OCAxMC0xMFMxNy41MiAyIDEyIDJ6bTAgMThjLTQuNDEgMC04LTMuNTktOC04czMuNTktOCA4LTggOCAzLjU5IDggOC0zLjU5IDgtOCA4eiIvPjxwYXRoIGQ9Ik0xNi4yIDkuNEwxMiAxMmw0LjIgMi42bC0yLjYgNC4ybC0yLjYtMi42LTQuMiAyLjZ2LTIuNi00LjJ6Ii8+PC9zdmc+)
[![Stars](https://img.shields.io/github/stars/jpueberbach4/bp.markets.ingest?style=social)](https://github.com/jpueberbach4/bp.markets.ingest)