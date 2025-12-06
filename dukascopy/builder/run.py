#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
File:        run.py
Author:      JP Ueberbach
Created:     2025-12-06
Description: Batch extraction utility for symbol/timeframe datasets.

This module provides a command-line interface for selecting, filtering, and
extracting data files based on symbol and timeframe patterns. All intermediate
outputs as well as final merged output files are written in **Parquet format**,
optionally using user-selected compression codecs.

The extraction process is parallelized using a multiprocessing worker pool with
progress tracking provided by tqdm.

High-level workflow:

1. Parse and validate command-line arguments, including:
   - date range filters
   - symbol/timeframe select expressions
   - compression options
   - safety flags (e.g. --force, --dry-run)
   - other flags (e.g. --omit-open-candles, --partition)

2. Discover all symbol/timeframe combinations that exist on disk and match
   the provided selection expressions. Selections that match no files will
   cause the program to abort unless --force is specified.

3. Construct a task list describing the extraction work to be performed, where
   each task includes:
   - symbol
   - timeframe
   - date range
   - output filename (Parquet)
   - other options

4. Initialize a multiprocessing pool and dispatch extraction tasks to workers,
   displaying progress via tqdm. Any worker error is considered critical and
   aborts the entire extraction process.

5. Optionally, partition output according to strategy
   (TODO: see on what gives best performance).

6. Merge all intermediate Parquet files produced by workers into final
   aggregated Parquet output OR if --partition is set, partition by symbol and TF.

7. Clean up temporary or intermediate files unless explicitly requested to
   keep them.

8. Present a status report summarizing wall-time and other statistics

Example usage:

    python3 run.py \
        --select EUR-USD/1m \
        --select EUR-NZD/4h,8h \
        --select BRENT.CMD-USD/15m,30m \
        --select BTC-*/15m \
        --select DOLLAR.IDX-USD/1h,4h \
        --after "2025-01-01 00:00:00" \
        --until "2025-12-01 12:00:00" \
        --output my_cool_parquet_file.parquet \    # single file, --partition not set
        --output_dir parquet/id                    # output_dir, --partition set
        --omit-open-candles \
        --dry-run \
        --compression zstd

This module's main() function implements the full workflow and is invoked when
run as a standalone script.

**Note**: AI Recommendation: Stick to symbol and a time-based key (like year/month) as the primary partition keys. 
Store timeframe as a regular column inside the Parquet files. Let's see what works best.
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path
import re
from typing import List, Tuple, Dict, Any

class CustomArgumentParser(argparse.ArgumentParser):
    """
    ArgumentParser subclass that prints the full help message whenever a parsing
    error occurs.

    This improves user experience by:
      - Showing the specific error message first
      - Displaying the complete help/usage output automatically
      - Exiting with status code 2 (standard argparse error code)

    The behavior is useful for CLI tools where incorrect arguments should
    provide immediate, fully detailed guidance without requiring users to
    rerun the command with --help.
    """
    def error(self, message):
        sys.stderr.write(f'Error: {message}\n\n')
        self.print_help(sys.stderr)
        sys.exit(2) 

def get_available_data_from_fs() -> List[Tuple[str, str, str]]:
    """
    Discover all available CSV datasets in the filesystem.

    The function scans the following directory structure:
      data/
        aggregate/1m/
        resample/<timeframe>/

    It identifies all CSV files under these directories and returns a list of
    tuples in the form:
        (symbol, timeframe, absolute_file_path)

    Returns:
        A sorted list of unique (symbol, timeframe, file_path) tuples.
    """
    data_dir = Path("data")
    if not data_dir.is_dir():
        return []
    
    available_data: List[Tuple[str, str, str]] = []
    
    # Base scan list: only 1m aggregate data is guaranteed to exist.
    scan_dirs = {
        "1m": data_dir / "aggregate" / "1m",
    }
    
    # Dynamically add all directories under data/resample/* as timeframes.
    resample_base = data_dir / "resample"
    if resample_base.is_dir():
        for tf_path in resample_base.iterdir():
            if tf_path.is_dir():
                # Directory name (e.g., "5m", "1h") is the timeframe.
                scan_dirs[tf_path.name] = tf_path

    # Iterate through all known directories and collect CSV files.
    for timeframe, dir_path in scan_dirs.items():
        if dir_path.is_dir():
            for file_path in dir_path.glob("*.csv"):
                symbol = file_path.stem                    # Symbol name from filename
                file_path_str = str(file_path.resolve())   # Absolute path for portability
                available_data.append((symbol, timeframe, file_path_str))
            
    # Deduplicate results and sort for stable output.
    unique_data = sorted(list(set(available_data)))
    return unique_data

def parse_args():
    """
    Parse and validate all command-line arguments for the batch extraction utility.

    This function:
    - Defines all supported CLI arguments (selection rules, date filters,
      output options, compression settings, safety flags, etc.)
    - Enforces mutually exclusive output modes (--output vs --output_dir)
    - Validates date formats and chronological consistency
    - Ensures partitioning rules are respected
    - Returns a fully validated argparse.Namespace object
    """

    # Custom parser ensures full help text is printed on errors
    parser = CustomArgumentParser(
        description="Batch extraction utility for symbol/timeframe datasets.",
        formatter_class=argparse.RawTextHelpFormatter
    )

    # Multiple selection rules allowed: --select A/B,C --select X/D
    parser.add_argument(
        '--select',
        action='append',
        required=True,
        metavar='SYMBOL/TF1,TF2,...',
        help=(
            "Specify symbol and timeframe selections.\n"
            "Example: --select EUR-USD/1m,5m --select BTC-*/4h"
        )
    )

    # Optional time range filters
    parser.add_argument(
        '--after',
        type=str,
        help="Start date/time (inclusive). Format: 'YYYY-MM-DD HH:MM:SS'."
    )
    parser.add_argument(
        '--until',
        type=str,
        help="End date/time (exclusive). Format: 'YYYY-MM-DD HH:MM:SS'."
    )

    # User must choose exactly one output target
    output_group = parser.add_mutually_exclusive_group(required=True)
    
    output_group.add_argument(
        '--output',
        type=str,
        metavar='FILE_PATH',
        help="Write a single aggregated Parquet file (no partitioning)."
    )
    
    output_group.add_argument(
        '--output_dir',
        type=str,
        metavar='DIR_PATH',
        help="Write a partitioned Parquet dataset (requires --partition)."
    )
    
    # Compression codec for parquet output
    parser.add_argument(
        '--compression',
        type=str,
        default='zstd',
        choices=['snappy', 'gzip', 'brotli', 'zstd', 'lz4', 'none'],
        help="Compression codec for output Parquet files."
    )
    
    # Optionally drop the last candle if incomplete
    parser.add_argument(
        '--omit-open-candles',
        action='store_true',
        help="Exclude the latest (possibly incomplete) candle from each timeframe."
    )
    
    # Allows continuing when selection patterns match nothing
    parser.add_argument(
        '--force',
        action='store_true',
        help="Do not abort if a selection pattern matches no input files."
    )
    
    # Discovery-only mode
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help="Perform argument parsing and task discovery only; do not execute work."
    )

    # Enables Hive-style partitioning
    parser.add_argument(
        '--partition',
        action='store_true',
        help="Enable Hive-style partitioning (requires --output_dir)."
    )
    
    parser.add_argument(
        '--keep-temp',
        action='store_true',
        help="Retain intermediate files instead of cleaning them up."
    )

    args = parser.parse_args()
    
    date_format = "%Y-%m-%d %H:%M:%S"
    
    dt_after = None
    dt_until = None
    
    # Validate date strings and convert to datetime objects
    for arg_name in ['after', 'until']:
        date_str = getattr(args, arg_name)
        if date_str:
            try:
                dt_obj = datetime.strptime(date_str, date_format)
                if arg_name == 'after':
                    dt_after = dt_obj
                else:
                    dt_until = dt_obj
            except ValueError:
                parser.error(f"Argument --{arg_name}: Invalid date format. Must be '{date_format}'")

    # Ensure --after < --until
    if dt_after and dt_until:
        if dt_after >= dt_until:
            parser.error(
                f"Date range invalid: --after ({args.after}) must be strictly "
                f"before --until ({args.until})."
            )
            
    # Partition mode requires --output_dir exclusively
    if args.partition and not args.output_dir:
        parser.error("--partition requires the --output_dir argument.")
    
    # Without partitioning, user must output a single file
    if not args.partition and not args.output:
        parser.error("Without --partition, the --output argument is required.")

    # Load every (symbol, timeframe, path) from filesystem
    all_available_data = get_available_data_from_fs()

    # Extract all unique timeframes
    all_available_timeframes = sorted(list(set([d[1] for d in all_available_data])))
    if not all_available_timeframes:
        parser.error("No timeframes found in data directories. Pipeline hasn't created any data yet.")
    
    # Precompute existence map for fast membership checks
    available_pairs = set([(d[0], d[1]) for d in all_available_data])
    
    # Unique available symbols for wildcard matching
    available_symbols = sorted(list(set([d[0] for d in all_available_data])))
    if not available_symbols:
        parser.error("No data found in 'data/' directories. Please run the main pipeline first.")
    
    final_selections: List[Tuple[str, str, str]] = []
    
    # Collect all requested {symbol,timeframe} pairs for validation
    all_requested_pairs = set()

    for selection_str in args.select:
        # Enforce pattern "SYMBOL/TF1,TF2,..."
        if '/' not in selection_str:
            parser.error(f"Invalid --select format: '{selection_str}'. Must be SYMBOL/TF1,TF2,...")
            
        symbol_pattern, timeframes_str = selection_str.split('/', 1)
        timeframes = [tf.strip() for tf in timeframes_str.split(',')]

        # '*' timeframe means all available timeframes
        if '*' in timeframes:
            timeframes = all_available_timeframes

        # Convert wildcard pattern to regex
        regex_pattern = symbol_pattern.replace('.', r'\.').replace('*', r'.*')
        
        # Find all symbols matching wildcard pattern
        matches = [s for s in available_symbols if re.fullmatch(regex_pattern, s)]
        
        # Build requested pairs and resolve them to actual files
        for symbol in matches:
            for tf in timeframes:
                requested_pair = (symbol, tf)
                all_requested_pairs.add(requested_pair)
                
                # Only append if data exists on disk
                if requested_pair in available_pairs:
                    # Fetch actual path record
                    for data_tuple in all_available_data:
                        if data_tuple[0] == symbol and data_tuple[1] == tf:
                            final_selections.append(data_tuple)
                            break

    # Determine which requested pairs did not resolve to actual data
    resolved_pairs = set([(d[0], d[1]) for d in final_selections])
    unresolved_pairs = sorted(list(all_requested_pairs - resolved_pairs))

    if unresolved_pairs:
        # TODO: implement behavior when --force is provided
        error_msg = "\nCritical Error: The following requested Symbol/Timeframe pairs could not be resolved to existing data files:\n"
        for symbol, tf in unresolved_pairs:
            error_msg += f"- {symbol}/{tf} (File not found on disk)\n"
        parser.error(error_msg)

    # Deduplicate and sort for stable output
    final_selections = sorted(list(set(final_selections)))
        
    return {
        'select_data': final_selections, 
        'after': args.after,
        'until': args.until,
        'output': args.output,
        'compression': args.compression,
        'omit_open_candles': args.omit_open_candles,
    }

def main():
    try:
        # Read and validate arguments, discover all file (symbol,tf) matches based on --select (TODO: --force)
        result = parse_args()
        # construct task list for workers, fork_extract(symbol, tf, after, until, to_filename, options )
        # initialize multiprocessing pool
        # execute tasks in pool with tqdm (progress tracking)
        # wait for pool to complete, raised errors by workers are critical and cause abort
        # todo: see on partition strategy
        # merge all pool output files to single parquet (skip if --partition set)
        # cleanup intermediate files
        # present user with status report
        print(result)

        
    except SystemExit as e:
        # Catch SystemExit which is raised on error, print status for user
        if e.code == 0:
            pass
        elif e.code == 2:
            print("\nExiting due to command-line syntax error.")
        else:
            raise

if __name__ == "__main__":
    main()
