#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        run.py
 Author:      JP Ueberbach
 Created:     2025-12-13
 Description: Main entry point for the Dukascopy batch extraction utility.

              This script handles the end-to-end workflow for extracting, 
              transforming,and exporting historical market data from Dukascopy 
              CSV files into Parquet or CSV formats. It supports multiprocessing, 
              optional MT4 output, and flexible output partitioning.

              Workflow:
              1. Enforce Terms of Service acceptance
              2. Load configuration
              3. Parse command-line arguments
              4. Build extraction tasks
              5. Dispatch tasks in parallel using a process pool
              6. Merge or partition extracted data
              7. Optional MT4 segregation
              8. Cleanup and report runtime
 Usage:
    pyhton3 run.py

 Requirements:
     - Python 3.8+
     - tqdm

 License:
     MIT License
===============================================================================
"""
import os
import time
from multiprocessing import get_context
from pathlib import Path
from tqdm import tqdm

from args import parse_args
from config.app_config import load_app_config
from extract import fork_extract
from merge import merge_output_files
from mt4 import export_and_segregate_mt4
from tos import require_tos_acceptance

# Number of worker processes used for extraction
NUM_PROCESSES = os.cpu_count()


def main():
    """
    Execute the full Dukascopy extraction workflow.

    Steps:
    - Enforces TOS acceptance.
    - Loads YAML configuration and command-line arguments.
    - Builds extraction tasks for selected symbols/timeframes.
    - Executes tasks in parallel using a multiprocessing pool.
    - Merges or partitions results according to output configuration.
    - Optionally exports results in MT4-compatible format.
    - Reports runtime statistics.

    Handles keyboard interrupts and argument parsing errors gracefully.
    """
    try:
        # Record start time
        start_time = time.time()

        # Require user to accept Terms of Service before proceeding
        require_tos_acceptance()

        # Load application configuration
        # User config overrides default
        if Path("config.user.yaml").exists():
            config = load_app_config('config.user.yaml')
        else:
            config = load_app_config('config.yaml')
        
        config = app_config.builder

        # Parse and validate command-line arguments
        options = parse_args(config)

        print(f"Running Dukascopy PARQUET/CSV exporter ({NUM_PROCESSES} processes)")

        # Build extraction tasks: (symbol, timeframe, file, after, until, modifier, options)
        extract_tasks = [
            (sym, tf, filename, options['after'], options['until'], modifier, options)
            for sym, tf, filename, modifier in options['select_data']
        ]

        # Create a shared multiprocessing context with fork method
        ctx = get_context("fork")
        pool = ctx.Pool(processes=NUM_PROCESSES)

        # Define pipeline stages (currently only extraction)
        stages = [("Extract", fork_extract, extract_tasks, 1, "files")]

        # Execute pipeline stages with progress bars
        with pool:
            for name, func, tasks, chunksize, unit in stages:
                if not tasks:
                    print(f"Skipping {name} (no tasks)")
                    continue
                try:
                    print(f"Step: {name}...")
                    for _ in tqdm(
                        pool.imap_unordered(func, tasks, chunksize=chunksize),
                        total=len(tasks),
                        unit=unit,
                        colour='white'
                    ):
                        pass
                except Exception as e:
                    print(f"\nABORT! Critical error in {name}.\n{type(e).__name__}: {e}")
                    break

        # Merge results if not partitioned
        if not options['partition']:
            print(f"Merging {options['output_dir']} to {options['output']}...")
            if not options['dry_run']:
                Path(options['output']).parent.mkdir(parents=True, exist_ok=True)

                merge_output_files(
                    Path(options['output_dir']),
                    options['output'],
                    options['output_type'],
                    options['compression'],
                    not options['keep_temp']
                )
            else:
                print(f"Skipping merge (dry-run)")

            # Optional MT4 export
            if options['mt4']:
                if not options['dry_run']:
                    export_and_segregate_mt4(Path(options['output']))
                else:
                    print(f"Skipping MT4 export (dry-run)")
                if not options['keep_temp']:
                    Path(options['output']).unlink(missing_ok=True)

        # Report total runtime
        elapsed = time.time() - start_time
        print("\nExport complete!")
        print(f"Total runtime: {elapsed:.2f} seconds ({elapsed / 60:.2f} minutes)")

    except KeyboardInterrupt:
        # Handle user interrupt (Ctrl+C)
        print("")
        return False
    except SystemExit as e:
        # Handle argparse/system exit codes
        if e.code == 2:
            print("\nExiting due to command-line syntax error.")
        elif e.code != 0:
            raise
    except Exception as e:
        # Catch-all for unexpected errors
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
