## Parquet/CSV export (v0.4 and above)

A powerful new utility, build-parquet.sh, allows you to generate high-performance .parquet files or partitioned Hive-style Parquet datasets based on your selection criteria.

>A new script, ```./build-csv.sh```, is available for generating CSV output. It accepts the same command-line arguments as ```./build-parquet.sh```. This script also supports ```--mt4``` flag for MT4/5 compatible CSV output.

**Note:** for this utility to work you need to install DuckDB

```sh
pip install -r requirements.txt
```

Example usage

List the available symbols

```sh
./build-csv.sh --list
```

Build a mixed symbol, mixed timeframe parquet file

```sh
./build-parquet.sh --select EUR-USD/1m --select EUR-NZD/4h:skiplast,8h:skiplast --select BRENT.CMD-USD/15m,30m \
--select BTC-USD/15m --select DOLLAR.IDX-USD/1h,4h --after "2025-01-01 00:00:00" \
--until "2025-12-01 12:00:00" --output my_cool_parquet_file.parquet --compression zstd
```

```sh
usage: build-(parquet|csv).sh [-h] (--select SYMBOL/TF1,TF2:modifier,... | --list) 
       [--after AFTER] [--until UNTIL] [--output FILE_PATH] [--output_dir DIR_PATH]
       [--csv | --parquet] [--compression {snappy,gzip,brotli,zstd,lz4,none}] [--mt4] 
       [--force] [--dry-run] [--partition] [--keep-temp]

Batch extraction utility for symbol/timeframe datasets.

optional arguments:
  -h, --help            show this help message and exit
  --select SYMBOL/TF1,TF2:modifier,...
                        Defines how symbols and timeframes are selected for extraction.
  --list                Dump out all available symbol/timeframe pairs and exit.
  --after AFTER         Start date/time (inclusive). Format: YYYY-MM-DD HH:MM:SS (Default: 1970-01-01 00:00:00)
  --until UNTIL         End date/time (exclusive). Format: YYYY-MM-DD HH:MM:SS (Default: 3000-01-01 00:00:00)
  --csv                 Write as CSV.
  --parquet             Write as Parquet (default).
  --compression {snappy,gzip,brotli,zstd,lz4,none}
                        Compression codec for Parquet output.
  --mt4                 Splits merged CSV into files compatible with MT4.
  --force               Allow patterns that match no files.
  --dry-run             Parse/resolve arguments only; do not run extraction.
  --partition           Enable Hive-style partitioned output (requires --output_dir).
  --keep-temp           Retain intermediate files.

Output Configuration (Required for Extraction Mode):
  --output FILE_PATH    Write a single merged output file.
  --output_dir DIR_PATH
                        Write a partitioned dataset.

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

>Use build-parquet.sh to convert raw CSV data into a format that’s ready for high-performance analysis.

```sh
python3 -c "
import duckdb
df = duckdb.sql(\"\"\"
    SELECT * FROM 'my_cool_parquet_file.parquet' WHERE timeframe='1m' AND symbol='EUR-USD' ORDER BY time DESC LIMIT 40;
  \"\"\").df()
print(df)
"
```

**Advice:** For large selects, use a hive.

>**❗Use the modifier ```skiplast``` to control whether the last (potentially open) candle should be dropped from a timeframe. \
❗Skiplast only has effect when --until is not set or set to a future datetime**

**Note on MT4 support** You can now use the ```--mt4``` flag to split CSV output into MetaTrader-compatible files. This flag works only with ```./build-csv.sh``` and cannot be used with ```--partition```. It has been implemented as an additional step following the merge-csv process.

```sh
./build-csv.sh --select EUR-USD/8h,1h:skiplast,4h:skiplast --output temp/csv/test.csv \
--after "2020-01-01 00:00:00" --mt4

....

Starting MT4 segregation process...
  ✓ Exported: temp/csv/test_EUR-USD_4h.csv
  ✓ Exported: temp/csv/test_EUR-USD_1h.csv
  ✓ Exported: temp/csv/test_EUR-USD_8h.csv

tail temp/csv/test_EUR-USD_1h.csv -n 5
2025.12.10,17:00:00,1.16431,1.16512,1.16345,1.16418,6978.43
2025.12.10,18:00:00,1.16419,1.16499,1.16372,1.16498,4455.46
2025.12.10,19:00:00,1.16499,1.16601,1.16456,1.16587,3285.91
2025.12.10,20:00:00,1.16586,1.16609,1.16535,1.16552,3237.46
2025.12.10,21:00:00,1.16549,1.1681,1.16467,1.16782,24032.88
```

>You now have your own local forex high-performance analytics and data stack. Don't forget to thank Dukascopy.


## DuckDB (Advanced users)

**Following the introduction of Parquet support, this section will be revised. CSV files now function only as a lightweight storage format.**

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
