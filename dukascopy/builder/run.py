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
        # Parse the string timestamps into real datetime objects
        dt_after = datetime.strptime(args.after, date_format) if args.after else None
        dt_until = datetime.strptime(args.until, date_format) if args.until else None
    except ValueError:
        parser.error(f"Invalid date format. Expected: {date_format}")

    # Enforce valid chronological ordering
    if dt_after and dt_until and dt_after >= dt_until:
        parser.error("--after must be strictly earlier than --until")

    # Enforce required pairing between --partition and --output_dir
    if args.partition and not args.output_dir:
        parser.error("--partition requires --output_dir")
    if not args.partition and not args.output:
        parser.error("Without --partition, --output must be provided")

    # Scan filesystem and collect all known (symbol, timeframe, path) triples
    all_available_data = get_available_data_from_fs()

    # Distinct symbols, timeframes, and (symbol,timeframe) pairs extracted from FS
    available_symbols = sorted({d[0] for d in all_available_data})
    available_timeframes = sorted({d[1] for d in all_available_data})
    available_pairs = {(d[0], d[1]) for d in all_available_data}

    if not available_symbols:
        parser.error("No datasets found in data/. Run the main pipeline first.")

    final_selections: List[Tuple[str, str, str, str | None]] = []
    all_requested_pairs_base = set()

    for selection_str in args.select:
        if '/' not in selection_str:
            parser.error(f"Invalid format: {selection_str} (expected SYMBOL/TF[:modifier])")
            
        symbol_pattern, timeframes_str = selection_str.split('/', 1)

        # Example: "1h:skiplast" → ["1h:skiplast", "4h", ...]
        timeframes_specs = [tf.strip() for tf in timeframes_str.split(',')]
        
        base_timeframes = []
        for tf_spec in timeframes_specs:
            # Extract bare timeframe (before any :modifier)
            base_tf = tf_spec.split(':')[0]
            base_timeframes.append(base_tf)

        # Expand "*" timeframe to all available timeframes
        if '*' in base_timeframes:
            timeframes_specs = available_timeframes[:]  # expand to full set
            base_timeframes = available_timeframes[:]   # same as above

        # Convert wildcard pattern to regex for symbol matching
        regex_pattern = symbol_pattern.replace('.', r'\.').replace('*', r'.*')

        # Match symbols based on wildcard-expanded regex
        matches = [s for s in available_symbols if re.fullmatch(regex_pattern, s)]
        if not matches:
            # Track selections that matched no symbol, useful for error reporting
            all_requested_pairs_base.add((symbol_pattern, timeframes_str))

        for symbol in matches:
            for tf_spec in timeframes_specs:
                base_tf = tf_spec.split(':')[0]       # base timeframe
                modifier = tf_spec.split(':')[1] if ':' in tf_spec else None  # optional modifier

                requested_base = (symbol, base_tf)
                all_requested_pairs_base.add(requested_base)

                # Find the actual file path for this (symbol, base_tf)
                if requested_base in available_pairs:
                    # Iterate original FS metadata to get exact path for the pair
                    for tup in all_available_data:
                        if tup[0] == symbol and tup[1] == base_tf:
                            # Append (symbol, full tf_spec, file path, modifier)
                            final_selections.append((symbol, base_tf, tup[2], modifier))
                            break

    # Extract only base timeframe (strip modifiers) for resolution checking
    resolved_pairs = {(d[0], d[1].split(':')[0]) for d in final_selections}

    # Determine which requested pairs could not be matched to actual data
    unresolved_pairs = sorted(all_requested_pairs_base - resolved_pairs)

    if unresolved_pairs and not args.force:
        error_msg_pairs = []
        for sym, tf_spec in unresolved_pairs:
            # Attempt to find how the user originally wrote the timeframe (with modifiers)
            original_spec = next((s for s in timeframes_specs if s.startswith(tf_spec)), tf_spec)
            error_msg_pairs.append(f"- {sym}/{original_spec}\n")
        
        msg = (
            "\nCritical Error: The following selections match no existing files:\n"
            + "".join(error_msg_pairs)
        )
        parser.error(msg)
    

    return {
        'select_data': sorted(set(final_selections)),   # sorted unique selections
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
        start_time = time.time()

        options = parse_args()
        print(f"Running Dukascopy PARQUET exporter ({NUM_PROCESSES} processes)")

        # Not partition handling? we need to set a temp output directory
        if not options['partition']:
            options['output_dir'] = f"temp/parquet/{uuid.uuid4()}"

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

    except SystemExit as e:
        if e.code == 2:
            print("\nExiting due to command-line syntax error.")
        elif e.code != 0:
            raise


if __name__ == "__main__":
    main()
