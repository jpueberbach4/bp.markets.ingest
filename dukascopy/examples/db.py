#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Install DuckDB first (its really awesome)

pip install duckdb

Module for constructing DuckDB OHLCV views from resampled CSV price data
and performing example analytical queries.

This script:

1. Connects to a DuckDB database (`dukascopy.db`).
2. Scans the ../data/resample directory for available timeframes
   (excluding "1m", which uses a different source path).
3. For each timeframe, dynamically creates or replaces a DuckDB VIEW
   named `ohlcv_<tf>` using CSV files from the corresponding folder.
   Each view provides:
        - symbol  : extracted from filename
        - ts      : parsed timestamp
        - open    : OHLCV price fields
        - high
        - low
        - close
        - volume

4. Demonstrates DuckDB queries:
        - DESCRIBE schema for a specific OHLCV view (15m).
        - Retrieve sample rows for EUR-USD (15m).
        - Compute RSI(14) for EUR-USD (4h) entirely inside DuckDB
          using window functions and inline aggregation.

Paths used:
    ../data/resample/<tf>/*.csv     for all timeframes except 1m
    ../data/aggregate/1m/*.csv      for 1m data

This script is intended for market-data analysis pipelines where
DuckDB views act as a lightweight database layer over CSV-based OHLCV
data, enabling SQL-native technical analysis.
"""
import duckdb
from pathlib import Path

con = duckdb.connect(database='dukascopy.db', read_only=False)

data_dir = Path("../data/resample")
timeframes = [p.name for p in data_dir.iterdir() if p.is_dir() and p.name != "1m"]

for tf in timeframes + ["1m"]:
    pattern = f"../data/resample/{tf}/*.csv" if tf != "1m" else "../data/aggregate/1m/*.csv"
    con.execute(f"""
        CREATE OR REPLACE VIEW ohlcv_{tf} AS
        SELECT 
            split_part(split_part(filename, '/', -1),'.',1) AS symbol,
            TRY_STRPTIME(timestamp, '%Y-%m-%d %H:%M:%S') AS ts,
            open, high, low, close, volume
        FROM read_csv('{pattern}', filename=true, columns={{'timestamp':'VARCHAR','open':'DOUBLE','high':'DOUBLE','low':'DOUBLE','close':'DOUBLE','volume':'DOUBLE'}})
    """)

print("Duckdb: showing column from ohlcv_15m")
df = con.execute("""
--- Show column names from ohlcv_15m
DESCRIBE ohlcv_15m
""").fetchdf()

print(df)

print("Duckdb: printing last 10 rows for EUR-USD (15m)")
df = con.execute("""
-- Latest 10 prices from EUR-USD 15m
SELECT symbol, ts, open, high, low, close, volume
    FROM ohlcv_15m WHERE symbol='EUR-USD' ORDER BY ts DESC LIMIT 10
""").df()

print(df)

print("Duckdb: print the RSI(14) of EUR-USD (4h)")
df = con.execute("""
-- Latest RSI(14) in just ONE query
SELECT 
    round(100 - 100 / (1 + avg_gain / nullif(avg_loss, 0)), 4) AS rsi_14
FROM (
    SELECT 
        avg(CASE WHEN delta > 0 THEN delta ELSE 0 END) AS avg_gain,
        avg(CASE WHEN delta < 0 THEN -delta ELSE 0 END) AS avg_loss
    FROM (
        SELECT 
            close - lag(close) OVER (ORDER BY ts) AS delta
        FROM ohlcv_4h
        WHERE symbol='EUR-USD'
        ORDER BY ts DESC
        LIMIT 14
    ) changes
) stats;
""").df()

print(df)

# Etc...