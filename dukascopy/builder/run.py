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


def merge_parquet_files(input_dir: Path, output_file: str, compression: str, cleanup: bool) -> int:
    """
    Reads all temporary Parquet files from input_dir and merges them 
    into a single final Parquet file using DuckDB.

    Args:
        input_dir: Path to the directory containing temporary Parquet files.
        output_file: The final destination filename (e.g., 'my_cool_file.parquet').
        compression: The compression codec to use for the final file.

    Returns:
        int: The number of files successfully merged.
    """
    input_files = list(input_dir.glob("**/*.parquet"))
    if not input_files:
        print(f"Warning: No temporary Parquet files found in {input_dir}. Nothing to merge.")
        return 0

    # DuckDB's read_parquet function accepts a list of file paths.
    input_pattern = str(input_dir / "**" / "*.parquet")
    
    con = duckdb.connect(database=':memory:')
    
    try:
        # The query reads all matching Parquet files and executes a COPY TO statement.
        merge_query = f"""
            COPY (
                SELECT * FROM read_parquet('{input_pattern}', union_by_name=true)
                ORDER BY time ASC
            )
            TO '{output_file}' 
            (
                FORMAT PARQUET,
                COMPRESSION '{compression.upper()}',
                ROW_GROUP_SIZE 1000000
            );
        """
        con.execute(merge_query)
        
        return len(input_files)

    except Exception as e:
        print(f"Critical error during consolidation: {e}")
        raise
        
    finally:
        if cleanup:
            for filename in input_files:
                Path(filename).unlink()
            shutil.rmtree(input_dir)

        con.close()


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
        help="Defines how symbols and timeframes are selected. Wildcards (*) are supported.\nThe skiplast modifier can be applied to exclude the last row of a timeframe."
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

    parser.add_argument(
        '--compression', type=str, default='zstd',
        choices=['snappy', 'gzip', 'brotli', 'zstd', 'lz4', 'none'],
        help="Compression codec for Parquet output."
    )

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

    # These flags must be paired correctly depending on output mode
    if args.partition and not args.output_dir:
        parser.error("--partition requires --output_dir")
    if not args.partition and not args.output:
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
            # We have a wildcard
            wildcard_modifier = ''
            # Loop through specs to get *:modifier
            for tf_spec in timeframes_specs:
                if '*' in tf_spec:
                    modifier_part = tf_spec.split(':')
                    if len(modifier_part) > 1:
                        # we have a modifier
                        wildcard_modifier = f":{modifier_part[1]}"
                    break # we do not support multiple wildcards in tf per select eg EUR-USD/*,*:skiplast.

            # Append the modifier to each timeframe 
            timeframes_specs = [f"{tf}{wildcard_modifier}" for tf in available_timeframes]
            base_timeframes = available_timeframes[:] # This line is now correct
        
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
    
    return {
        'select_data': sorted(final_selections), 
        'partition': args.partition,
        'output_dir': args.output_dir,
        'dry_run': args.dry_run,
        'force': args.force,
        'keep_temp': args.keep_temp,
        'after': args.after,
        'until': args.until,
        'output': args.output,
        'compression': args.compression
    }


def require_tos_acceptance():
    """
    Prompts the user to accept the Terms of Service and loops until a 
    valid affirmative response ('yes' or 'y') is received, or exits on denial.
    """

    if Path("cache/HAS_ACCEPTED_TERMS_OF_SERVICE").exists():
        return True

    print("=" * 70)
    print("TERMS OF SERVICE & LEGAL DISCLAIMER")
    print("=" * 70)
    
    print("\nLEGAL DISCLAIMER")
    print("-" * 26)
    print("This software is provided 'as is' for educational and research purposes only.")
    print("It does not constitute trading advice, investment recommendations, or execution functionality.")
    
    print("\nIMPORTANT NOTICE")
    print("-" * 26)
    print("This tool downloads and processes data that is freely provided by Dukascopy Bank SA.")
    print("Users are solely responsible for complying with Dukascopy's Terms of Service and all applicable laws.")
    print("The author is not affiliated with Dukascopy Bank SA.")
    print("This software itself does not redistribute Dukascopy's raw data.")
    
    print("\nSTRICTLY PROHIBITED")
    print("-" * 26)
    prohibited_actions = [
        "Commercial redistribution of data in any form (raw, processed, aggregated,",
        "  resampled, CSV, Parquet, DuckDB, etc.).",
        "Publishing, sharing, uploading, torrenting, or mirroring any datasets",
        "  generated by this tool — even if modified or enriched.",
        "Hosting generated files on public cloud storage, GitHub releases,",
        "  Hugging Face, Kaggle, torrents, or any publicly accessible location.",
        "Incorporating data produced by this tool into commercial products,",
        "  SaaS platforms, signal services, copy-trading systems, paid newsletters,",
        "  or any offering provided to third parties for compensation.",
        "Using this tool to create competing data services or commercial data products."
    ]
    for action in prohibited_actions:
        print(action)
    
    print("\nADDITIONAL OBLIGATIONS")
    print("-" * 26)
    print("Respect all rate limits and server load considerations.")
    print("Commercial entities requiring historical market data must obtain")
    print("  proper licenses from authorized vendors.")
    
    print("\nREVOCATION CLAUSE")
    print("-" * 26)
    print("If Dukascopy Bank SA or any competent authority requests removal or")
    print("restriction of this software, the author reserves the right to")
    print("immediately delist the repository and all releases without prior notice.")
    
    print("\n" + "=" * 70)
    print("By using the Parquet Exporter, you agree to these Terms of Service.")
    print("=" * 70)
    
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
            print("\n✗ Terms were not accepted. Aborting Parquet export.")
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
        print(f"Running Dukascopy PARQUET exporter ({NUM_PROCESSES} processes)")

        # Not partition handling? we need to set a temp output directory
        if not options['partition']:
            options['output_dir'] = f"data/temp/parquet/{uuid.uuid4()}"

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
        
        # TODO: implement merging / partition assembly
        if not options['partition']:
            print(f"Merging {options['output_dir']} to {options['output']}...")
            merge_parquet_files(Path(options['output_dir']), options['output'], options['compression'], not options['keep_temp'])

            pass

        elapsed = time.time() - start_time
        print("\nExport complete!")
        print(f"Total runtime: {elapsed:.2f} seconds ({elapsed/60:.2f} minutes)")

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
