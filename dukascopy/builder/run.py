#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
File:        run.py
Author:      JP Ueberbach
Created:     2025-12-06
Description: Batch extraction utility for symbol/timeframe datasets.

This module implements a command-line workflow for discovering, filtering,
extracting, and exporting historical market datasets stored as CSV files.  
Extraction is performed in parallel using a multiprocessing worker pool, and
all exported results are written in Parquet format.

High-Level Workflow
-------------------
1. **Argument Parsing**
   - Validate symbol/timeframe selection expressions
   - Validate date filters
   - Validate mutually exclusive output modes
   - Validate compression, partitioning, and safety flags

2. **Dataset Discovery**
   - Scan `data/aggregate/1m` and all `data/resample/<tf>/` directories
   - Match discovered files against user selection rules
   - Abort (unless `--force` is used) if selections resolve to no files

3. **Task Construction**
   Each extraction task contains:
       - symbol
       - timeframe
       - source CSV path
       - date filters
       - execution flags

4. **Parallel Extraction**
   - Dispatch tasks to workers using a shared process pool
   - Track progress with tqdm
   - Abort immediately on worker failure

5. **Output Assembly**
   - If `--output`: merge extracted subsets into a single Parquet file
   - If `--output_dir --partition`: write a partitioned Parquet dataset

6. **Cleanup and Reporting**
   - Remove temporary files unless `--keep-temp` is used
   - Print total runtime and basic statistics

Example:
    python3 run.py \
        --select EUR-USD/1m \
        --select BTC-*/15m:skiplast \
        --after "2025-01-01 00:00:00" \
        --until "2025-12-01 12:00:00" \
        --output merged.parquet \
        --compression zstd \
        --dry-run

Note:
    Preliminary recommendation: Use `symbol` and a time-based component
    (e.g., year-month) as partition keys. Store timeframe as a column
    inside the Parquet files. Actual performance characteristics remain
    subject to tuning.
"""

import argparse
import duckdb
import extract
import os
import re
import sys
import time
import uuid
import shutil
from datetime import datetime
from multiprocessing import get_context
from pathlib import Path
from tqdm import tqdm
from typing import List, Tuple, Dict, Any


# Number of worker processes used throughout the pipeline
NUM_PROCESSES = os.cpu_count()


class CustomArgumentParser(argparse.ArgumentParser):
    """
    ArgumentParser subclass that prints the full help text whenever a parsing
    error occurs.

    This improves CLI usability by:
      - Showing the exact error message
      - Automatically printing full help/usage output
      - Exiting with a standard argparse error code (2)

    Users therefore receive immediate guidance without needing to rerun
    the command with --help.
    """
    def error(self, message):
        sys.stderr.write(f'{message}\n\n')
        self.print_help(sys.stderr)
        sys.exit(2)


def get_available_data_from_fs() -> List[Tuple[str, str, str]]:
    """
    Scan the filesystem and return all available CSV datasets.

    Expected directory structure:
        data/
            aggregate/1m/*.csv
            resample/<timeframe>/*.csv

    Each CSV file corresponds to a dataset for a given symbol and timeframe.

    Returns:
        List of tuples:
            (symbol, timeframe, absolute_path)
        Sorted and deduplicated.
    """
    data_dir = Path("data")
    if not data_dir.is_dir():
        return []
    
    available_data: List[Tuple[str, str, str]] = []
    
    # Always scan 1m aggregate directory (base resolution)
    scan_dirs = {
        "1m": data_dir / "aggregate" / "1m",
    }
    
    # Add all discovered resample timeframes (e.g., "5m", "1h", "4h", ...)
    resample_base = data_dir / "resample"
    if resample_base.is_dir():
        for tf_path in resample_base.iterdir():
            if tf_path.is_dir():
                scan_dirs[tf_path.name] = tf_path

    # Collect (symbol, timeframe, absolute path) for all CSVs
    for timeframe, dir_path in scan_dirs.items():
        if dir_path.is_dir():
            for file_path in dir_path.glob("*.csv"):
                symbol = file_path.stem
                available_data.append(
                    (symbol, timeframe, str(file_path.resolve()))
                )
            
    return sorted(set(available_data))

def merge_output_files(input_dir: Path, output_file: str, output_type: str, compression: str, cleanup: bool) -> int:
    """
    Merge all temporary Parquet or CSV files from a directory into a single output file
    using DuckDB.

    The function identifies all files matching the requested output_type within
    input_dir (recursively), loads them through DuckDB's readers, sorts the combined
    dataset by the `time` column, and writes the result to output_file using the
    specified compression settings. Parquet merges are performed with union-by-name
    semantics to accommodate schema drift between shards.

    Args:
        input_dir:
            Directory containing temporary Parquet or CSV files to merge.
        output_file:
            Path to the final merged output file that will be written.
        output_type:
            Output format for the merged file. Must be either 'parquet' or 'csv'
            (case-insensitive).
        compression:
            Compression codec to apply to the final file (e.g., 'zstd', 'gzip', 
            'snappy', depending on DuckDB support).
        cleanup:
            If True, deletes all temporary files and removes input_dir after a 
            successful or failed merge attempt.

    Returns:
        int:
            The number of input files found and merged into the final output.

    Raises:
        ValueError:
            If an unsupported output_type is provided.
        Exception:
            If DuckDB encounters an error during the merge or write process.
    """

    # Normalize case early for consistency in comparisons
    output_type = output_type.upper()
    compression = compression.upper()
    
    # Determine which file extension and DuckDB reader to use
    # Using glob patterns allows DuckDB to read many files in a single call
    if output_type == 'PARQUET':
        input_pattern = str(input_dir / "**" / "*.parquet")   # Recursive glob for all Parquet shards
        read_function = "read_parquet"                        # DuckDB function name used in SQL context
    elif output_type == 'CSV':
        input_pattern = str(input_dir / "**" / "*.csv")
        read_function = "read_csv_auto"                       # Auto-detect CSV schema
    else:
        raise ValueError(f"Unsupported output type for merging: {output_type}")

    # Collect file paths to count them and confirm something exists to merge
    input_files = list(input_dir.glob(f"**/*.{output_type.lower()}"))

    if not input_files:
        # Early exit avoids creating an empty output file
        print(f"Warning: No temporary {output_type} files found in {input_dir}. Nothing to merge.")
        return 0

    # Build COPY TO settings and reader options depending on output type
    if output_type == 'PARQUET':
        # Parquet supports additional tuning such as row group size
        format_options = f"""
            FORMAT PARQUET,
            COMPRESSION '{compression}',
            ROW_GROUP_SIZE 1000000
        """
        # Ensures safe merging even when files differ slightly in schemas
        read_options = ", union_by_name=true"
    elif output_type == 'CSV':
        # CSV requires explicit HEADER and DELIMITER declarations in DuckDB
        format_options = f"""
            FORMAT CSV,
            HEADER true,
            DELIMITER ',',
            COMPRESSION '{compression}'
        """
        # No CSV-specific merge options needed
        read_options = ""

    # Use an in-memory DuckDB instance to avoid writing intermediary data
    con = duckdb.connect(database=':memory:')
    
    try:
        # COPY query reads all files via glob, merges them, sorts on 'time', and writes once.
        # DuckDB handles parallelization and columnar batching internally.
        merge_query = f"""
            COPY (
                SELECT * FROM {read_function}('{input_pattern}'{read_options})
                ORDER BY time ASC   -- final unified ordering
            )
            TO '{output_file}' 
            (
                {format_options}
            );
        """

        # Execute the merge; this performs the full consolidation in one SQL command
        con.execute(merge_query)
        
        # Return the number of shards successfully merged
        return len(input_files)

    except Exception as e:
        # Log the error before raising to preserve traceback
        print(f"Critical error during consolidation: {e}")
        raise
        
    finally:
        if cleanup:
            print(f"Cleaning up temporary directory: {input_dir}")
            try:
                # Remove the directory containing the temporary partitions
                shutil.rmtree(input_dir)
            except OSError as e:
                # Cleanup failures shouldn’t mask merge failures
                print(f"Error during cleanup of {input_dir}: {e}")

        # Ensure DuckDB connection is closed even if an error occurred
        con.close()

def export_and_segregate_mt4(merged_file_path: Path):
    """
    Segregates a merged CSV of trading data into MT4-compliant CSV files by symbol and timeframe.

    This function reads a merged CSV file containing multiple symbols and timeframes,
    identifies all unique symbol/timeframe pairs, and exports each pair to a separate
    6-column CSV file formatted for MetaTrader 4 (MT4). The exported files do not include
    headers and follow the date/time formatting required by MT4.

    Output filenames are constructed as: <MERGED_FILENAME>_<SYMBOL>_<TIMEFRAME>.csv
    For example, a merged file "all_data.csv" containing EUR-USD with 8H timeframe
    would result in "all_data_EUR-USD_8H.csv".

    Parameters:
    -----------
    merged_file_path : Path
        Path to the merged CSV file containing all symbols and timeframes.

    Returns:
    --------
    int
        The total number of successfully exported MT4 CSV files.

    Raises:
    -------
    None
        All exceptions are caught and logged; the function will return 0 if an error occurs.
    """
    # Connect to an in-memory DuckDB database
    con = duckdb.connect(database=':memory:')
    
    print("\nStarting MT4 segregation process...")

    # Query to discover all unique symbol/timeframe combinations in the merged CSV
    discover_query = f"""
        SELECT DISTINCT symbol, timeframe
        FROM read_csv_auto('{merged_file_path}', union_by_name=true);
    """
    try:
        # Execute the discovery query and fetch all results
        results = con.execute(discover_query).fetchall()
    except Exception as e:
        # Handle errors if the query fails
        print(f"Error discovering symbols/timeframes in merged file: {e}")
        con.close()
        return 0

    # If no symbols/timeframes found, exit early
    if not results:
        print("Warning: No data found to segregate for MT4.")
        con.close()
        return 0
        
    count = 0  # Counter for successful exports

    # Loop through each symbol/timeframe pair
    for symbol, timeframe in results:

        # Extract the base filename (without extension) from the merged file path
        stem = Path(merged_file_path).stem

        # Construct the output filename for MT4 CSV
        output_filename = f"{stem}_{symbol}_{timeframe}.csv"
        
        # Full output path for the exported file
        output_path = Path(merged_file_path).parent / output_filename
        
        # Query to transform the merged CSV into MT4 6-column format and export it
        mt4_transform_query = f"""
            COPY (
                SELECT
                    strftime(time, '%Y.%m.%d') AS Date,  -- Format date as YYYY.MM.DD
                    strftime(time, '%H:%M') AS Time,     -- Format time as HH:MM
                    open,                                -- Open price
                    high,                                -- High price
                    low,                                 -- Low price
                    close                                -- Close price
                FROM read_csv_auto('{merged_file_path}', union_by_name=true)
                WHERE symbol = '{symbol}' AND timeframe = '{timeframe}'
                ORDER BY date asc, time ASC            -- Ensure chronological order
            )
            TO '{output_path}'
            (
                FORMAT CSV,
                HEADER false,                          -- MT4 requires no header row
                DELIMITER ','                           -- CSV comma delimiter
            );
        """
        try:
            # Execute the export query
            con.execute(mt4_transform_query)
            print(f"  ✓ Exported: {output_path}")
            count += 1
        except Exception as e:
            # Handle any errors during export
            print(f"  ✗ Failed to export {symbol}/{timeframe}: {e}")
            
    # Close the DuckDB connection
    con.close()
    
    # Return the total number of successfully exported files
    return count



def parse_args():
    """
    Parse and validate all command-line arguments.
    """
    parser = CustomArgumentParser(
        description="Batch extraction utility for symbol/timeframe datasets.",
        formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument(
        '--select',
        action='append',
        required=True,
        metavar='SYMBOL/TF1,TF2:modifier,...',
        help="Defines how symbols and timeframes are selected. Wildcards (*) are NOT supported.\nThe skiplast modifier can be applied to exclude the last row of a timeframe."
    )

    DEFAULT_AFTER = "1970-01-01 00:00:00"
    DEFAULT_UNTIL = "3000-01-01 00:00:00"

    parser.add_argument('--after', type=str, default=DEFAULT_AFTER,
                        help=f"Start date/time (inclusive). Format: YYYY-MM-DD HH:MM:SS (Default: {DEFAULT_AFTER})")
    parser.add_argument('--until', type=str, default=DEFAULT_UNTIL,
                        help=f"End date/time (exclusive). Format: YYYY-MM-DD HH:MM:SS (Default: {DEFAULT_UNTIL})")

    output_group = parser.add_mutually_exclusive_group(required=True)
    output_group.add_argument('--output', type=str, metavar='FILE_PATH',
                              help="Write a single merged Parquet file.")
    output_group.add_argument('--output_dir', type=str, metavar='DIR_PATH',
                              help="Write a partitioned Parquet dataset.")

    type_group = parser.add_mutually_exclusive_group(required=False)
    type_group.add_argument('--csv', action='store_const', const='csv', dest='output_type', help="Write as CSV.")
    type_group.add_argument('--parquet', action='store_const', const='parquet', dest='output_type', help="Write as Parquet (default).")

    parser.add_argument(
        '--compression', type=str, default='zstd',
        choices=['snappy', 'gzip', 'brotli', 'zstd', 'lz4', 'none'],
        help="Compression codec for Parquet output."
    )

    parser.add_argument('--mt4', action='store_true',
                        help="Splits merged CSV into files compatible with MT4.")

    parser.add_argument('--force', action='store_true',
                        help="Allow patterns that match no files.")
    parser.add_argument('--dry-run', action='store_true',
                        help="Parse/resolve arguments only; do not run extraction.")
    parser.add_argument('--partition', action='store_true',
                        help="Enable Hive-style partitioned output (requires --output_dir).")
    parser.add_argument('--keep-temp', action='store_true',
                        help="Retain intermediate files.")

    args = parser.parse_args()
    
    date_format = "%Y-%m-%d %H:%M:%S"
    try:
        # Convert string timestamps to real datetime objects for validation
        dt_after = datetime.strptime(args.after, date_format) if args.after else None
        dt_until = datetime.strptime(args.until, date_format) if args.until else None
    except ValueError:
        parser.error(f"Invalid date format. Expected: {date_format}")

    # Ensure user-defined time window is chronologically valid
    if dt_after and dt_until and dt_after >= dt_until:
        parser.error("--after must be strictly earlier than --until")

    # Default to Parquet output
    if args.output_type is None:
        args.output_type = 'parquet'

    # Validate Compression against Output Type
    compression_choices = {
        'parquet': ['snappy', 'gzip', 'brotli', 'zstd', 'lz4', 'none', 'uncompressed'],
        'csv': ['none', 'uncompressed', 'gzip', 'zstd'] # Common CSV compressions
    }
    
    if args.compression not in compression_choices.get(args.output_type, ['none']):
        parser.error(
            f"Compression '{args.compression}' is not suitable for output type '{args.output_type}'. "
            f"Valid options are: {', '.join(compression_choices.get(args.output_type, ['none']))}"
        )

    # These flags must be paired correctly depending on output mode
    if args.partition and not args.output_dir:
        parser.error("--partition requires --output_dir")

    # Yeah, parameter stuff.... defensive programming.... :S
    if not args.partition and args.output_dir:
        parser.error("--output_dir requires --partition")

    if args.partition and args.mt4:
        parser.error("--mt4 incompatible with --partition")

    if args.output_type == 'parquet' and args.mt4:
        parser.error("--parquet incompatible with --mt4")

    if not args.partition and not args.output:
        if args.output_type == 'parquet':
            parser.error("Without --partition, --output must be provided")

    # Load (symbol, timeframe, file_path) entries from the filesystem
    all_available_data = get_available_data_from_fs()

    # Build sets for fast lookup & matching during pattern expansion
    available_symbols = sorted({d[0] for d in all_available_data})
    available_timeframes = sorted({d[1] for d in all_available_data})
    available_pairs = {(d[0], d[1]) for d in all_available_data}

    if not available_symbols:
        parser.error("No datasets found in data/. Run the main pipeline first.")

    # Stores final deduplicated selection, with modifier-priority resolution
    priority_map: Dict[Tuple[str, str], Tuple[str, str, str, str | None]] = {} 

    # Used to detect unresolved selections for error reporting
    all_requested_pairs_base = set()

    for selection_str in args.select:
        if '/' not in selection_str:
            parser.error(f"Invalid format: {selection_str} (expected SYMBOL/TF[:modifier])")
            
        symbol_pattern, timeframes_str = selection_str.split('/', 1)

        # User may supply multiple TF definitions in a single --select
        timeframes_specs = [tf.strip() for tf in timeframes_str.split(',')]
        
        # Extract base timeframe (e.g. "H1" from "H1:skiplast")
        base_timeframes = []
        for tf_spec in timeframes_specs:
            base_tf = tf_spec.split(':')[0]
            base_timeframes.append(base_tf)

        # Wildcard timeframes, select all timeframes that actually exist
        is_wildcard_select = any('*' in tf_spec.split(':')[0] for tf_spec in timeframes_specs)

        if is_wildcard_select:
            print("The * timeframe wildcard is currently unsupported")
            raise
        
        # Temporarily disable wildcard select
        if '*' in symbol_pattern:
            print("The * symbol wildcard is currently unsupported")
            raise


        # Convert wildcard symbol pattern to a regex (e.g. "BTC*" → "^BTC.*$")
        regex_pattern = symbol_pattern.replace('.', r'\.').replace('*', r'.*')

        # Find all actual symbols matching user pattern
        matches = [s for s in available_symbols if re.fullmatch(regex_pattern, s)]

        # If no symbol matched user request, track for reporting (unless --force)
        if not matches:
            all_requested_pairs_base.add((symbol_pattern, timeframes_str))

        for symbol in matches:
            for tf_spec in timeframes_specs:
                base_tf = tf_spec.split(':')[0]       # Bare timeframe
                modifier = tf_spec.split(':')[1] if ':' in tf_spec else None  # Optional modifier

                
                requested_base = (symbol, base_tf)
                all_requested_pairs_base.add(requested_base)

                if requested_base in available_pairs:
                    # Locate its file path in the filesystem metadata
                    for tup in all_available_data:
                        if tup[0] == symbol and tup[1] == base_tf:
                            new_task = (symbol, base_tf, tup[2], modifier)

                            # Pull existing task's modifier, if any
                            current_modifier = priority_map.get(
                                requested_base, (None, None, None, None)
                            )[3]
                            #   - If no modifier yet, or new entry *has* a modifier → overwrite
                            #   - If existing entry already had a modifier and new one does not → keep existing
                            if current_modifier is None or modifier is not None:
                                priority_map[requested_base] = new_task
                            break
    
    # Convert deduplicated selection map to list
    final_selections = list(priority_map.values())

    # Determine which requests never resolved to real files
    resolved_pairs = set(priority_map.keys())
    unresolved_pairs = sorted(all_requested_pairs_base - resolved_pairs)

    if unresolved_pairs and not args.force:
        # Build detailed error message showing unresolved symbol/timeframe specs
        error_msg_pairs = []
        for sym, tf_spec in unresolved_pairs:
            error_msg_pairs.append(f"- {sym}/{tf_spec}\n") 
        
        msg = (
            "\nCritical Error: The following selections match no existing files:\n"
            + "".join(error_msg_pairs)
        )
        parser.error(msg)
    
    # fix compression = none -> uncompressed
    # bug/todo: compression-mode CSV fails (no compression supported atm for CSV) on merge
    # check that select statement (in copy to, see above) for incoming CSV compression support
    if args.compression == "none" or args.output_type == "csv":
        args.compression = "uncompressed"

    return {
        'select_data': sorted(final_selections), 
        'partition': args.partition,
        'output_dir': args.output_dir,
        'output_type': args.output_type,
        'dry_run': args.dry_run,
        'force': args.force,
        'keep_temp': args.keep_temp,
        'after': args.after,
        'until': args.until,
        'output': args.output,
        'compression': args.compression,
        'mt4': args.mt4
    }


def require_tos_acceptance():
    """
    Prompts the user to accept the Terms of Service and loops until a 
    valid affirmative response ('yes' or 'y') is received, or exits on denial.
    """

    if Path("cache/HAS_ACCEPTED_TERMS_OF_SERVICE").exists():
        return True

    print("\n" + "="*70)
    print("🚀 TERMS OF SERVICE")
    print("="*70)
    print("""
1. This tool provides access to Dukascopy Bank SA's historical data.
2. Data is for PERSONAL, NON-COMMERCIAL research/analysis ONLY.
3. REDISTRIBUTION IN ANY FORM IS STRICTLY PROHIBITED.
4. You accept full liability for your usage.
5. Dukascopy's own Terms of Service apply.
6. THE TOOL AND DATA ARE PROVIDED 'AS IS' WITHOUT ANY WARRANTIES, 
   EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO WARRANTIES OF 
   MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, OR ACCURACY.
    
By using this tool, you accept these terms.
    """)
    # Loop indefinitely until a valid input is provided
    while True:
        # Prompt the user for input and convert to lowercase for easy checking
        response = input("\nDo you accept the Terms of Service? (yes/no): ").strip().lower()

        if response in ['yes', 'y']:
            print("\n✓ Terms accepted. Continuing with data extraction...")
            # Ensure cache directory exists
            Path("cache").mkdir(parents=True, exist_ok=True)
            with open("cache/HAS_ACCEPTED_TERMS_OF_SERVICE", "w"):
                pass
            return True  # Return success
            
        elif response in ['no', 'n']:
            print("\n✗ Terms were not accepted. Aborting.")
            sys.exit(1) # Exit the script with a non-zero status code (error)
            
        else:
            print("Invalid input. Please respond with 'yes' or 'no'.")

def main():
    """
    Execute the full extraction workflow.

    - Parse arguments and resolve dataset selections
    - Build the extraction task list
    - Dispatch tasks to workers in a shared process pool
    - Merge/partition results depending on output options
    - Report total runtime
    """
    try:
        require_tos_acceptance()
        start_time = time.time()

        options = parse_args()

        print(f"Running Dukascopy PARQUET/CSV exporter ({NUM_PROCESSES} processes)")

        # Not partition handling? we need to set a temp output directory
        if not options['partition']:
            options['output_dir'] = f"data/temp/{options['output_type']}/{uuid.uuid4()}"

        # Build list of extraction tasks for workers
        extract_tasks = [
            (sym, tf, filename, options['after'], options['until'], modifier, options)
            for sym, tf, filename, modifier in options['select_data']
        ]

        # Use a single shared multiprocessing context for all stages
        ctx = get_context("fork")
        pool = ctx.Pool(processes=NUM_PROCESSES)

        stages = [
            ("Extract", extract.fork_extract, extract_tasks, 1, "files")
        ]

        # Run pipeline stages with progress bars
        with pool:
            for name, func, tasks, chunksize, unit in stages:
                if not tasks:
                    print(f"Skipping {name} (no tasks)")
                    continue
                try:
                    print(f"Step: {name}...")
                    for _ in tqdm(
                        pool.imap_unordered(func, tasks, chunksize=chunksize),
                        total=len(tasks), unit=unit, colour='white'
                    ):
                        pass
                except Exception as e:
                    print(f"\nABORT! Critical error in {name}.\n{type(e).__name__}: {e}")
                    break
        
        # Merge
        if not options['partition']:
            print(f"Merging {options['output_dir']} to {options['output']}...")
            # Personally, i dont like cli programs
            if not Path(options['output']).parent.exists():
                Path(options['output']).parent.mkdir(parents=True, exist_ok=True)
            # Now, go merge!
            merge_output_files(Path(options['output_dir']), options['output'], options['output_type'], options['compression'], not options['keep_temp'])
            if options['mt4']:
                # And,.. split again for metatrader (not optimal, bit hacky, but works)
                export_and_segregate_mt4(options['output'])
                if not options['keep_temp']:
                    Path(options['output']).unlink(missing_ok=True)

        elapsed = time.time() - start_time
        print("\nExport complete!")
        print(f"Total runtime: {elapsed:.2f} seconds ({elapsed/60:.2f} minutes)")

    except Exception as e:
        print(f"Error {e}")
    except KeyboardInterrupt:
        print("")
        return False
    except SystemExit as e:
        if e.code == 2:
            print("\nExiting due to command-line syntax error.")
        elif e.code != 0:
            raise


if __name__ == "__main__":
    main()
