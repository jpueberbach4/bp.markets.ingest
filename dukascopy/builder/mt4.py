#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        mt4.py
 Author:      JP Ueberbach
 Created:     2025-12-13
 Description: Module to handle MT4-specific CSV exports from merged Dukascopy 
              datasets.

              This module reads a merged dataset (CSV or Parquet) and segregates 
              it into individual MT4-compatible CSV files, one per symbol and 
              timeframe. It also applies a time shift for weekly bars (1W) to 
              align with MT4 conventions.

 Requirements:
     - Python 3.8+
     - duckdb

 License:
     MIT License
===============================================================================
"""
import duckdb
from pathlib import Path

def export_and_segregate_mt4(merged_file_path: Path) -> int:
    """
    Export merged Dukascopy dataset into MT4-compatible CSV files.

    Parameters:
    -----------
    merged_file_path : Path
        Path to the merged CSV file containing multiple symbols/timeframes.

    Returns:
    --------
    int
        Number of successfully exported MT4 files.

    Operations:
    -----------
    - Discovers distinct symbols and timeframes in the merged file.
    - Creates one CSV file per (symbol, timeframe) combination.
    - Applies a time shift for weekly bars (1W) to align with MT4.
    - Orders the CSV by date and time.
    - Outputs CSVs without headers, as required by MT4.
    """
    # Connect to an in-memory DuckDB instance
    con = duckdb.connect(database=":memory:")
    print("\nStarting MT4 segregation process...")

    # Query to discover all unique symbol/timeframe combinations
    discover_query = f"""
        SELECT DISTINCT symbol, timeframe
        FROM read_csv_auto('{merged_file_path}', union_by_name=true);
    """

    try:
        results = con.execute(discover_query).fetchall()
    except Exception as e:
        print(f"Error discovering symbols/timeframes in merged file: {e}")
        con.close()
        return 0

    if not results:
        print("Warning: No data found to segregate for MT4.")
        con.close()
        return 0

    count = 0

    for symbol, timeframe in results:
        # Prepare output CSV file path
        stem = merged_file_path.stem
        output_path = merged_file_path.parent / f"{stem}_{symbol}_{timeframe}.csv"

        # Apply time shift for weekly bars (1W) to align with MT4
        time_expr = "time - INTERVAL 1 DAY" if timeframe == "1W" else "time"

        # DuckDB COPY query to generate MT4 CSV
        copy_query = f"""
            COPY (
                SELECT
                    strftime({time_expr}, '%Y.%m.%d') AS Date,
                    strftime({time_expr}, '%H:%M:%S') AS Time,
                    open,
                    high,
                    low,
                    close,
                    volume
                FROM read_csv_auto('{merged_file_path}', union_by_name=true)
                WHERE symbol = '{symbol}' AND timeframe = '{timeframe}'
                ORDER BY date ASC, time ASC
            )
            TO '{output_path}'
            (
                FORMAT CSV,
                HEADER false,
                DELIMITER ','
            );
        """

        try:
            # Execute the export
            con.execute(copy_query)
            suffix_msg = " - Shifted to Sunday to line up" if timeframe == "1W" else ""
            print(f"  ✓ Exported: {output_path}{suffix_msg}")
            count += 1
        except Exception as e:
            print(f"  ✗ Failed to export {symbol}/{timeframe}: {e}")

    # Close the DuckDB connection
    con.close()
    return count
