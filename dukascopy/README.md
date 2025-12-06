## Table of Contents

- [Notice (Important)](#notice)
- [Introduction](#introduction)
- [What Is This Tool Used For?](#what-is-this-tool-used-for)
- [Target audience](#target-audience)
- [Server Kindness](#server-kindness)
- [Key Design Principles](#key-design-principles)
- [Quick Start](#quick-start)
  - Dependencies & Installation
  - Directory Permissions
  - First Run & Incremental Mode
  - Automatic Updates (cron)
- [Symbols Configuration](#symbols-configuration)
  - Adding New Symbols
- [Pipeline Configuration](#pipeline-configuration-v03-and-above)
  - Overriding timeframes, etc
- [Output schema](#output-schema)
  - Details on generated files
- [Quick Check](#quick-check)
- [Parquet converter](#parquet-converter-v04-and-above)
  - Details on CSV->Parquet conversion
- [Performance Benchmarks](#performance-benchmarks)
  - Cold Run (Full History)
  - Incremental Daily Update
  - TMPFS Pro Tip
- [Fail-Fast](#fail-fast)
- [Directory Structure](#directory-structure)
- [Troubleshooting](#troubleshooting)
  - Stale Locks
  - Full Rebuild
- [Future Work](#notes-and-future-work)
- [DuckDB Analytical Layer (Advanced)](#duckdb-advanced-users)
- [Bug Tracking](#bug-tracking)
- [Final Word](#final-word)
- [License](#license)


## Notice

if you cloned this repo before 2025-12-04 and are having trouble to sync, please update carefully:

```bash
git fetch origin
git reset --hard origin/main
```

>Note: when you use the default configuration, data-points are now exactly aligned to https://www.dukascopy.com/swiss/english/marketwatch/charts/

## Notice

Backfilling is not currently supported, as our pipeline processes data strictly forward. Because of this, historical data—particularly for illiquid pairs and at the highest granularity—may be skewed. Backfilling has been identified as a must-have feature.

We'll provide a script that should be executed once every seven days (run on saturdays). It will re-download the past week of data for all configured symbols and perform a full rebuild. This captures any backfills within that window, effectively addressing ~99.94-99.97% of all backfill issues.

For reference, running this on 26 symbols takes about five minutes (or around 2 minutes 30 seconds if you’re up to date and use the rebuild script)—a small price to pay for accuracy.

```python
Major FX         █░░░░░░░░░ 0.01%  (1 in 7,000-12,500 symbol-days)
Major Crosses    ███░░░░░░░ 0.05%
Illiquid FX      ██████████ 1.1%
Indices          ██░░░░░░░░ 0.09%
Major Crypto     ██████████ 1.3%
Altcoins         ████████████████ 3.5%
```

```sh
crontab -e
```
Add the following line, adjust path accordingly:

```sh
0 1 * * 6 cd /home/repos/bp.markets.ingest/dukascopy && ./rebuild-weekly.sh
```

This configuration triggers the rebuild script at 01:00 each Saturday. It will not conflict with the per-minute ./run.sh cron entry (due to locking). For additional assurance, you may choose to run it daily. Overall, the setup is now far more robust in terms of integrity.

>This is a universal challenge in market-data engineering. Even when working with top-tier, premium data vendors, the moment you download or extract data and begin using it, some portion of it may already be stale due to backfills. It’s an inherent property of financial datasets, not a limitation of this tool. There is no central log or official feed that reliably exposes all historical corrections, making automated detection non-trivial. As a result, every data pipeline—paid or free—must contend with this reality.

The quality of this dataset is on par with what you would receive from commercial providers. The difference is simply that this one is free.

---

## What Is This Tool Used For?

>This tool builds a high-quality historical OHLCV dataset and maintains it automatically with efficient incremental updates. 

Historical market data can be leveraged in multiple ways to enhance analysis, decision-making, and trading performance:

- **Backtesting** → Evaluate and refine trading strategies by simulating them on past market conditions. This helps determine whether a strategy is robust, profitable, and resilient across different market environments.

- **Technical Analysis** → Use historical charts to identify trends, chart patterns, support- and resistance levels. You can also perform correlation studies to compare long-term relationships between currency pairs or other assets.

- **Seasonal Analysis** → Detect recurring market behaviors or unusual pricing patterns that tend to appear during specific months, weeks, or seasons.

- **Volatility Assessment** → Analyze historical volatility to adjust risk parameters, optimize position sizing, and set more accurate stop-loss levels.

- **Computational Intelligence** → Build machine-learning or statistical models trained on historical price data to forecast potential market movements.

- **Economic Event Impact** → Study how past economic releases, geopolitical events, and news shocks influenced currency pairs — helping you prepare for similar situations in the future.

---

## Target audience

This tool was built for independent traders and quants—like myself—who need to analyze market data daily and absolutely hate manually downloading files. It's ideal for laptop users running Windows (and WSL2) with around 32GB of RAM and a Ryzen 7/9 or Intel equivalent, having NVMe storage. Designed for simplicity, it automatically updates your data, so you can open your laptop, grab your coffee, and know you're ready for the day's market without any extra steps.

>Storage requirements are about 1 GB per configured symbol.

The code-base is small and heavily documented.

---

## Server Kindness

[Dukascopy SA](https://www.dukascopy.com) has been providing this priceless data **for free since 2003** with no paywall and no API key. This entire pipeline only exists because of their generosity.

If you find this tool useful, please consider:

- Trying their platform (I’ve been a happy client for years — support is actually human and fast)
- Running the script no more than once per hour unless you truly need minute-level updates

These two small acts keep the data flowing for everyone, forever.
Thank you — and thank you, Dukascopy.

---

## Key Design Principles

- **CSV-based storage** → Simplifies resume logic via file offsets
- **Incremental processing** → Only new/missing data is handled
- **Pointer tracking** → Enables precise continuation across runs
- **Zero backtracking** → Data is only processed/read once
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
| `duckdb`   | >=1.3.2    | Analytical database layer on top of CSV + parquet building helper           |
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

**Permissions**

These scripts read from and write to both the data directory and the cache directory. If your system uses strict permission settings, ensure that the ./data directory is created in advance.

```sh
mkdir -p ./data ./cache
chown -R $USER:$USER ./data ./cache
chmod u+rwx ./data ./cache
```
---

Configure your symbols as shown in the next section of this readme.

>[Symbols Configuration](#symbols-configuration)

Next, run the pipeline with:

```sh
START_DATE=2005-01-01 ./run.sh
```

>Running run.sh without a START_DATE means incremental mode.

Optionally, configure a cronjob for periodical execution: 

```sh
crontab -e
```

Add the following line, adjust path accordingly:

```sh
* * * * * sleep 5 && cd /home/repos/bp.markets.ingest/dukascopy && ./run.sh
```
---

## Symbols Configuration

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

We stop our crontab service for a moment or comment the line for run.sh in crontab. Next, we add the symbol as a new row in symbols.user.txt. Next, run the pipeline using:

```sh
START_DATE=2005-01-01 ./run.sh
```

The pipeline will begin downloading the symbol's historical data (this may take some time) and then execute the remaining steps.

The new symbol is now added and will be updated automatically during each incremental run.

>When you don't stop the crontab periodic execution before changing the symbol list, you will need to rebuild!

---

## Pipeline Configuration (v0.3 and above)

A default ```config.yaml``` is included with the project. This file controls the behavior of the aggregate, download, transform and resample engine. You can now define custom timeframes and apply per-symbol overrides as needed.

To override the default configuration, create a user-specific copy:

```sh
cp config.yaml config.user.yaml
```

The configuration file is straightforward and mostly self-explanatory. Adjust values as needed to suit your data and workflow.

```yaml
## Below you will find the configuration for the aggregate.py script. 
aggregate:
  paths:
    data: data/aggregate/1m           # Output path for aggregate
    source: data/transform/1m         # Input path for aggregate
## Below you will find the configuration for the download.py script. 
download:
  max_retries: 3                      # Number of retries before downloader raises
  backoff_factor: 2                   # Exponential backoff factor (wait time)
  timeout: 10                         # Request timeout
  paths:
    historic: cache                   # Historical downloads
    live: data/temp                   # Live downloads
## Below you will find the configuration for the transform.py script. 
transform:
  round_decimals: 8                   # Number of decimals to round OHLCV to
  paths:
    data: data/transform/1m           # Output directory for transform
    historic: cache                   # Historical downloads
    live: data/temp                   # Live downloads
## Below you will find the configuration for the resample.py script. 
resample:
  round_decimals: 8                    # Number of decimals to round OHLCV to
  batch_size: 250000                   # Maximum number of lines to read per batch
  paths:
    data: data/resample                # Output directory for resampled timeframes
  timeframes:
    1m:
      source: "data/aggregate/1m"      # No rule, no resample, source defines output path for this timeframe
    5m:
      rule: "5T"                       # 5-minute timeframe (Pandas Resampling Rule)
      label: "left"                    # Label (timestamp) assigned to each resampled interval comes from the left (start) edge of the window
      closed: "left"                   # Window is left-inclusive, right-exclusive
      source: "1m"                     # Uses 1m timeframe as input (defines the cascading order)
    15m:
      rule: "15T"                      # 15-minute timeframe
      label: "left"
      closed: "left"
      source: "5m"                     # Uses 5m timeframe as input
    30m:
      rule: "30T"                      # And so on....
      label: "left"
      closed: "left"
      source: "15m"
    1h:
      rule: "1H"
      label: "left"
      closed: "left"
      source: "30m"
    4h:
      rule: "4H"
      label: "left"
      closed: "left"
      source: "1h"
    8h:
      rule: "8H"
      label: "left"
      closed: "left"
      source: "4h"
    1d:
      rule: "1D"
      label: "left"
      closed: "left"
      source: "8h"
    1W:
      rule: "W-MON"                    # Weekly, aligning candle close to Monday
      label: "left"
      closed: "left"
      source: "1d"
    1M:
      rule: "MS"                       # Monthly, beginning of the month
      label: "left"
      closed: "left"
      source: "1d"
    1Y:
      rule: "AS"                       # Annual, beginning of the year
      label: "left"
      closed: "left"
      source: "1M"

  # Support per symbol overrides
  symbols:
    BTC-USDXX:
      # Override number of decimal places to round to
      round_decimals: 12
      # Override batch size
      batch_size: 500000
      # Skip timeframes entirely for this symbol
      skip_timeframes: ["1W", "1M", "1Y"]
      # Support for custom timeframes or overrides
      timeframes:
        5h:
          rule: "5H"             # 5-hourly timeframe
          label: "left"
          closed: "left"
          source: "1h"
        1d:
          rule: "1D"
          label: "right"         # Different labeling for this specific symbol/timeframe
          closed: "left"
          source: "8h"
```

**Note**: if you change resample, make sure you put the timeframes in the right order, because the stages depend on each other. On each resample configuration change, perform a ```./rebuild-weekly.sh```.

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
- Timestamps are in UTC and follow YYYY-MM-DD HH:MM:SS format
- Price values are rounded to configurable decimal places (default: 8)
- Volume represents the total trading activity for the period

---

## Quick check

For users who are just getting started, or for those who want a quick way to validate their generated data:

**Example**. Suppose you’ve added **EURUSD** to your setup. All processes have run and completed, and now you want a quick look at the daily data it produced—perhaps to compare it against a source like Investing.com.

A simple way to do this is by using [csvplot.com](http://www.csvplot.com).

>In order to open the data directory in your Windows explorer, type ```explorer.exe ./data``` inside WSL.

Open the site in your browser and drag the daily EURUSD CSV file — found in **data/resample/1d** — into the CSV Plot window.

On the left side of the interface:

- Drag the **time** column to the x-axis

- Drag the **close** column to the y-axis

The chart will generate immediately. Use the control in the upper-right corner to change the display to a line chart. The result should resemble the following.

![Example-view](images/examplevieweurusd.png)

In the resampled output files, the final candle should be interpreted as an open candle. As new data enters the 1-minute aggregated file, it cascades into the higher-timeframe series, updating their respective open candles. This behavior is intentional, as tracking the open candle can be beneficial for certain trading strategies.

The open candle will always be the last row in the CSV. If you prefer not to include it for backtesting, simply omit this final row from your analysis.

---

## Parquet converter (v0.4 and above)

A powerful new utility, build-parquet.sh, allows you to generate high-performance .parquet files or partitioned Hive-style Parquet datasets based on your selection criteria.

**Note:** for this utility to work you need to install DuckDB

```sh
pip install -r requirements.txt
```

Example usage

```sh
./build-parquet.sh --select EUR-USD/1m --select EUR-NZD/4h,8h --select BRENT.CMD-USD/15m,30m \
--select BTC-*/15m --select DOLLAR.IDX-USD/1h,4h --after "2025-01-01 00:00:00" \
--until "2025-12-01 12:00:00" --omit-open-candles --output my_cool_parquet_file.parquet --compression zstd
```

```sh
usage: build-parquet.sh [-h] --select SYMBOL/TF1,TF2,... [--after AFTER] 
                        [--until UNTIL] (--output FILE_PATH | --output_dir DIR_PATH) 
                        [--compression {snappy,gzip,brotli,zstd,lz4,none}] [--omit-open-candles]
                        [--force] [--dry-run] [--partition] [--keep-temp]

Batch extraction utility for symbol/timeframe datasets.

optional arguments:
  -h, --help            show this help message and exit
  --select SYMBOL/TF1,TF2,...
                        Symbol/timeframe selection pattern. Supports '*' wildcards.
  --after AFTER         Start date/time (inclusive). Format: YYYY-MM-DD HH:MM:SS (Default: 1970-01-01 00:00:00)
  --until UNTIL         End date/time (exclusive). Format: YYYY-MM-DD HH:MM:SS (Default: 3000-01-01 00:00:00)
  --output FILE_PATH    Write a single merged Parquet file.
  --output_dir DIR_PATH
                        Write a partitioned Parquet dataset.
  --compression {snappy,gzip,brotli,zstd,lz4,none}
                        Compression codec for Parquet output.
  --omit-open-candles   Drop the newest candle if incomplete. (Works, with a caveat, see below)
  --force               Allow patterns that match no files
  --dry-run             Parse/resolve arguments only; do not run extraction.
  --partition           Enable Hive-style partitioned output (requires --output_dir).
  --keep-temp           Retain intermediate files.
```

**Schema:**

| Column | Type (Implied) | Type (Explicit) |
| :--- | :--- | :--- |
| symbol | Varchar (String) | VARCHAR (or STRING) |
| timeframe | Varchar (String) | VARCHAR (or STRING) |
| time | Timestamp (Timestamp) | TIMESTAMP |
| open, high, low, close | Double | DOUBLE |
| volume | Double | DOUBLE |

**Benefits:**

- Queries on Parquet are 25-50× faster than on CSV files.
- Ideal for complex analyses and large datasets.
- Supports partitioning by symbol and year for optimized querying.

>Use build-parquet.sh to convert raw CSV data into a format that’s ready for high-performance analysis. Use a quoted ```--select "*/*"``` if you need to export all symbols, all timeframes, within a date-range.

```sh
python3 -c "
import duckdb
df = duckdb.sql(\"\"\"
    SELECT * FROM 'my_cool_parquet_file.parquet' WHERE timeframe='1m' AND symbol='EUR-USD' ORDER BY time DESC LIMIT 40;
  \"\"\").df()
print(df)
"
```

**Advice:** For large selects, eg. a select ```"*/*"``` from 2005 until now: use output_dir (a hive). It will o/w likely choke on the merge. This is an edge case (select everything to a single parquet file) which we will not support atm. If it's really needed. For (very!) good reasons, drop me a line and i will see what i can do. A hive is the current solution for huge exports.

>```--omit-open-candles``` works fine on active trading days (when there is trading activity), but I still need to find an elegant solution for when markets are closed (e.g., during the weekend). For FX and indices, the last candles in the CSV on a Saturday are still Friday's candles, and these should be treated as closed. However, the current logic strips off the final candle by default, so running this on a Saturday incorrectly removes Friday's last candle across all lower timeframes. There's more to consider as well—such as the monthly timeframe when a month ends on a Friday. Another case is when considering the 1m (minute) timeframe. The 1m timeframe only has completed candles. And so on.... I'm currently compiling all edge cases and working on a proper solution. **For now, if you are beta testing, use this flag with caution.**

---

## Performance Benchmarks

### Cold Run (Full Update)

> **Hardware:** AMD Ryzen 7 (8C/16T) · 1 TB NVMe SSD · WSL2 (Ubuntu)  
> **Workload:** 20 years of 1-minute OHLC data · **26 symbols** (~520 years total)

| Script        | Time     | Unit/s (unit) | Candles/s (read)    | Data Written | Write Speed |
|---------------|----------|---------|---------------|--------------|-------------|
| `transform.py`| **89 s** | > 2,000 (files) | **1.35 M**   | 7.3 GB       | **82 MB/s** |
| `aggregate.py`| **24 s** | > 2,000 (files) | **5.0 M**   | 6.9 GB       | **260 MB/s** |
| `resample.py`| **122 s** | 0.21 (symbols) | **1 M**   | 2.3 GB       | **19 MB/s** |


**Total pipeline time:** **~3.9 minutes**  

**Throughput (stage average):** **> 1 million candles processed per second**

**Throughput (pipeline average):** **> 500 thousand candles processed per second**

>Excellent for commodity hardware.

### Incremental Run (Daily Update)
> **Workload:** 26 symbols × 1 day of new data

| Stage | Time | Throughput | Notes |
|-------|------|------------|-------|
| Download | 0.43s | 60.3 downloads/s | Network limited |
| Transform | 0.02s | **2,439 files/s** | Pure I/O speed |
| Aggregate | 0.01s | **2,122 symbols/s** | Pointer-based append |
| Resample | 0.21s | 118 symbols/s | 10 timeframes cascaded |
| **Total** | **0.67s** | - | **Sub-2-second updates** ⚡ |

>No NVMe but have loads of RAM (>64GB Free)? Put this on TMPFS. It will rock. Safe estimate: 20GB PER 25 symbols (20 years of data). 

> **Reproducible on any modern Ryzen 7 + NVMe setup.**

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

---

## Troubleshooting

### Stale Locks

If pipeline was interrupted (laptop sleep, SIGKILL) and you get "Another instance is already running", remove stale locks. This is a very unlikely event.

```bash
rm -rf data/locks/*.lck
```

### Rebuild from scratch?

Stop crontab (best practice) and

```bash
rm -rf ./data/*
START_DATE=2005-01-01 ./run.sh
```

### Performance Issues
- **Slow first run?** Normal - processing 20 years of data takes time
- **Slow incremental?** Check if NVMe/SSD. HDDs will be 10-50x slower
- **High CPU?** Reduce `NUM_PROCESSES` in scripts
- **Out of memory?** Reduce `BATCH_SIZE` in resample.py (default: 500K)

---

## Notes and Future Work

>HTTP API for OHLC retrieval

>Cascaded indicator engine

>Central backfill detection and redistribution service? Using Github? 

>MSSIB Extension for DuckDB


---

## DuckDB (Advanced users)

```sh
pip install duckdb
```

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
            split_part(split_part(filename, '/', -1),'.',1) AS symbol,
            TRY_STRPTIME(timestamp, '%Y-%m-%d %H:%M:%S') AS ts,
            open, high, low, close, volume
        FROM read_csv('{pattern}', filename=true, columns={{'timestamp':'VARCHAR','open':'DOUBLE','high':'DOUBLE','low':'DOUBLE','close':'DOUBLE','volume':'DOUBLE'}})
    """)

print("🚀 DuckDB warehouse ready — query with con.sql('SELECT ...')")

df = con.execute("""
-- Latest 10 rows from EUR-USD 15m (including open candle)
SELECT symbol, ts, open, high, low, close, volume
    FROM ohlcv_15m WHERE symbol='EUR-USD' ORDER BY ts DESC LIMIT 10
""").df()

print(df)

df = con.execute("""
-- Latest RSI(14) of EUR-USD 15m
SELECT 
    round(100 - 100 / (1 + avg_gain / nullif(avg_loss, 0)), 4) AS rsi_14
FROM (
    SELECT 
        avg(CASE WHEN delta > 0 THEN delta ELSE 0 END) AS avg_gain,
        avg(CASE WHEN delta < 0 THEN -delta ELSE 0 END) AS avg_loss
    FROM (
        SELECT 
            close - lag(close) OVER (ORDER BY ts) AS delta
        FROM ohlcv_15m
        WHERE symbol='EUR-USD'
        ORDER BY ts DESC
        LIMIT 14
    ) changes
) stats;
""").df()

print(df)

```
Outputs:

```sh
🚀 DuckDB warehouse ready — query with con.sql('SELECT ...')
>>>
>>> df = con.execute("""
... -- Latest 10 rows from EUR-USD 15m (including open candle)
... SELECT symbol, ts, open, high, low, close, volume
...     FROM ohlcv_15m WHERE symbol='EUR-USD' ORDER BY ts DESC LIMIT 10
... """).df()
>>>
>>> print(df)
    symbol                  ts     open     high      low    close   volume
0  EUR-USD 2025-12-02 16:00:00  1.16061  1.16075  1.16061  1.16075   117.75
1  EUR-USD 2025-12-02 15:45:00  1.16103  1.16127  1.16014  1.16061  1691.82
2  EUR-USD 2025-12-02 15:30:00  1.15998  1.16159  1.15998  1.16104  2547.17
3  EUR-USD 2025-12-02 15:15:00  1.16051  1.16064  1.15932  1.15995  2251.00
4  EUR-USD 2025-12-02 15:00:00  1.16178  1.16185  1.16027  1.16049  2229.39
5  EUR-USD 2025-12-02 14:45:00  1.16164  1.16185  1.16131  1.16177  1597.00
6  EUR-USD 2025-12-02 14:30:00  1.16184  1.16191  1.16143  1.16164  1688.86
7  EUR-USD 2025-12-02 14:15:00  1.16186  1.16194  1.16138  1.16183  1044.76
8  EUR-USD 2025-12-02 14:00:00  1.16175  1.16230  1.16162  1.16185  1774.17
9  EUR-USD 2025-12-02 13:45:00  1.16151  1.16174  1.16110  1.16174   864.74
>>>
>>> df = con.execute("""
... -- Latest RSI(14) of EUR-USD 15m
... SELECT
...     round(100 - 100 / (1 + avg_gain / nullif(avg_loss, 0)), 4) AS rsi_14
... FROM (
...     SELECT
...         avg(CASE WHEN delta > 0 THEN delta ELSE 0 END) AS avg_gain,
...         avg(CASE WHEN delta < 0 THEN -delta ELSE 0 END) AS avg_loss
...     FROM (
...         SELECT
...             close - lag(close) OVER (ORDER BY ts) AS delta
...         FROM ohlcv_15m
...         WHERE symbol='EUR-USD'
...         ORDER BY ts DESC
...         LIMIT 14
...     ) changes
... ) stats;
... """).df()
>>>
>>> print(df)
    rsi_14
0  40.8333
>>>
```

**Note**: A working example has been added to the examples directory to help you get started quickly.

**Tip 1**: You can paste this entire README into an LLM (such as Grok, ChatGPT, Claude, or any tool you use) to generate custom queries, indicators, backtesting code, or SQL for DuckDB.

After pasting the README, ask something like:

```sh
Now that you've ingested the full document:

In the DuckDB section, should I add SMA, EMA, MACD, RSI or other indicators?
Please generate SQL examples for these indicators using the resampled OHLCV files.
```

The LLM will then:

- Infer your dataset structure
- Understand the incremental resampling logic
- Use your directory layout
- Generate SQL tailored to your OHLCV format
- Adapt to any timeframe
- Produce examples of indicators, analytics, or joins

This avoids the need (for me) to maintain separate example files and allows users to explore any use-case. The responses are very accurate.

**Tip 2**: Performance Note: If you need higher query throughput, consider loading your symbols into in-memory tables first. DuckDB supports temporary, in-memory tables that can significantly improve performance by reducing repeated CSV scans. If you've worked with SQL before, you'll recognize this pattern—temporary tables behave like normal tables but live entirely in memory and disappear at session end.

```sql
CREATE TEMP TABLE candles_1h_eurusd AS 
SELECT *
FROM read_csv_auto('data/resample/1h/EUR-USD.csv');
```

**Tip 3 (final one)**: Some of you might be fairly new to (algo-)trading. Remember, LLM's are trained on  huge amounts of financial documents. Use that knowledge. It's easy to get it to teach you. 

**Example**. Paste the following in an LLM (i used Google Gemini for this one):

```sh
2025-11-21 00:00:00,1.15338,1.15524,1.14909,1.15155,115651.22
2025-11-23 00:00:00,1.15128,1.15143,1.15058,1.15073,2709.03
2025-11-24 00:00:00,1.15074,1.15503,1.15018,1.152,71212.85
2025-11-25 00:00:00,1.15201,1.15859,1.15114,1.15648,108585.88
2025-11-26 00:00:00,1.15648,1.16021,1.1547,1.16017,108027.31
2025-11-27 00:00:00,1.16018,1.16132,1.15763,1.15996,51613.66
2025-11-28 00:00:00,1.15995,1.16075,1.1555,1.15973,177674.44
2025-11-30 00:00:00,1.1594,1.16078,1.15912,1.1601,3303.65
2025-12-01 00:00:00,1.16011,1.16522,1.15893,1.16066,93031.96
2025-12-02 00:00:00,1.16069,1.1629,1.1591,1.1628,74084.42

analyze these prices and predict if next daily is up or down and elaborate why
```

It responds with:

```sh
Based on a technical analysis of the provided data, the prediction is that the next daily price is likely to be >UP<.

Price Analysis and Rationale
The analysis of the ten data points reveals a strong, consistent short-term uptrend. The prediction for an "Up" day is based on three key technical factors:

1. Clear Uptrend .... it reasons why.
```

It was actually correct and it gives you the information on how it came to it's conclusion. You can use it's response to fine-tune or implement your own strategies.

**WARNING: LLMs do not know the future — they analyze patterns you provide**

## Final word

Thank you for using this toolkit. The goal of the project is simple: provide a fast and fully transparent pipeline for high-quality historical market data. **This architecture prioritizes speed and simplicity via CSV output over the analytical performance of enterprise binary formats.** If you have ideas, find issues, or want to contribute, feel free to open a GitHub issue or pull request.

A more advanced, tick-ready successor—planned as a C++ DuckDB extension—is under development and will be announced when ready.

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




