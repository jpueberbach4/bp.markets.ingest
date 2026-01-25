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
  --select SYMBOL:modifier/TF1,TF2:modifier,...
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

Supported modifiers (optional):

  # Normalize gaps and Panama-backadjust a symbol
  SYMBOL:panama

  # Skip last candle from a timeframe
  TF:skiplast

Examples:

  # List all available symbols
  build-csv.sh --list

  # Extract raw 1m and 1h data for BRENT as a single .csv file
  build-csv.sh --select BRENT.CMD.USD/1m,1h --output brent_data.csv

  # Extract Panama-adjusted 1m data for BRENT as a single .Parquet file
  build-parquet.sh --select BRENT.CMD.USD:panama/1m --output panama_data.parquet

  # Extract raw 1m, 1h and 4h data for BRENT and exclude the last candle of 1h and 4h to .csv file
  build-csv.sh --select BRENT.CMD.USD/1m,1h:skiplast,4h:skiplast --output brent_data.csv

  # Select multiple symbols and multiple timeframes to .Parquet hive
  build-parquet.sh --select EUR-USD/1m,1h,4h --select DOLLAR.IDX-USD/1h --output_dir temp/export --partition

  # Extract raw 1m data for BRENT and EUR-USD and export it to mt4 .csv format
  build-csv.sh --select BRENT.CMD-USD/1m --select EUR-USD/1m --output brent_data.csv --mt4

  # Extract raw 1m data for EUR-USD for the month of December 2025 to .csv file
  build-csv.sh --select EUR-USD/1m --after "2025-12-01 00:00:00" --until "2026-01-01 00:00:00"  --output limit.csv

  # Extract Panama-adjusted 1h and 4h for BRENT and skiplast on all timeframes
  build-csv.sh --select BRENT.CMD-USD:panama:skiplast/1h,4h --dry-run --output panama_test.csv

  # Perform a dry-run to verify file discovery
  build-csv.sh --select EUR-USD/1h --dry-run --output test.csv

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