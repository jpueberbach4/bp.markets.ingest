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
import sys
from multiprocessing import get_context
from pathlib import Path
from tqdm import tqdm
from collections import defaultdict, deque
from args import parse_args
from config.app_config import load_app_config
from extract import fork_extract
from merge import merge_output_files
from mt4 import export_and_segregate_mt4
from tos import require_tos_acceptance

# Since we (potentially) import from ETL folder, we need to app a syspath
sys.path.append(str(Path(__file__).resolve().parent.parent))

def get_task_category(task):
    """Classify a pipeline task by processing complexity.

    Tasks are categorized based on the presence and type of modifiers, which
    determine how expensive the task is to execute.

    Categories:
        0: Adjusted tasks (require resampling and extraction)
        1: Modified tasks (extraction only, with modifiers)
        2: Naked tasks (no modifiers, fastest)

    Args:
        task (Sequence): A task descriptor where index 5 contains a collection
            of modifier strings.

    Returns:
        int: An integer category representing the task's processing priority.
    """
    # Extract modifier metadata from the task
    modifiers = task[5]

    # Adjusted tasks require the most processing
    if "panama" in modifiers:
        return 0

    # Tasks with other modifiers but not adjusted
    if modifiers:
        return 1

    # Tasks with no modifiers
    return 2

def optimize_pipeline_tasks(tasks):
    """Reorder pipeline tasks to optimize execution efficiency and concurrency.

    Tasks are categorized by processing cost and modifiers, then scheduled so
    that heavier tasks (e.g., adjusted/resampled) are executed first while
    interleaving work across symbols to avoid serial bottlenecks. Lightweight
    tasks without modifiers are deferred until the end.

    Categories:
        0: Adjusted tasks (highest cost)
        1: Tasks with modifiers but not adjusted
        2: Naked tasks (no modifiers)

    Args:
        tasks (Iterable[Sequence]): A collection of pipeline tasks. Each task is
            expected to contain a symbol identifier at index 0 and modifier
            metadata accessible to `get_task_category`.

    Returns:
        list: A reordered list of tasks optimized for concurrency and
        deterministic execution.
    """
    # Initialize buckets for each task category
    buckets = {0: defaultdict(deque), 1: defaultdict(deque), 2: []}

    # Classify tasks into buckets, grouping by symbol where applicable
    for t in tasks:
        cat = get_task_category(t)
        if cat == 2:
            buckets[2].append(t)
        else:
            buckets[cat][t[0]].append(t)

    final_queue = []

    # Interleave tasks in categories 0 and 1 using round-robin scheduling per symbol
    for cat in [0, 1]:
        symbol_map = buckets[cat]
        if not symbol_map:
            continue

        # Sort symbols to ensure deterministic task ordering
        symbols = sorted(symbol_map.keys())

        # Continue until all tasks in this category are consumed
        while any(symbol_map.values()):
            for symbol in symbols:
                if symbol_map[symbol]:
                    final_queue.append(symbol_map[symbol].popleft())

    # Append naked (no-modifier) tasks at the end
    final_queue.extend(buckets[2])

    return final_queue


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
        # TODO: Number of worker processes used for extraction
        NUM_PROCESSES = os.cpu_count()

        # Record start time
        start_time = time.time()

        # Require user to accept Terms of Service before proceeding
        require_tos_acceptance()

        # Load application configuration
        # User config overrides default
        if Path("config.user.yaml").exists():
            config_filename = "config.user.yaml"
            app_config = load_app_config('config.user.yaml')
        else:
            config_filename = "config.yaml"
            app_config = load_app_config('config.yaml')
        
        config = app_config.builder

        # Determine num_processes
        num_processes = os.cpu_count() if config.num_processes is None else config.num_processes

        # Parse and validate command-line arguments
        options = parse_args(config)

        # Store config filename in options
        options['config_file'] = config_filename

        print(f"Running Dukascopy PARQUET/CSV exporter ({NUM_PROCESSES} processes)")

        # Build extraction tasks: (symbol, timeframe, file, after, until, modifier, options)
        extract_tasks = [
            (sym, tf, filename, options['after'], options['until'], modifier, indicators, options)
            for sym, tf, filename, modifier, indicators in options['select_data']
        ]

        # Since we may resample because of adjusted flag, give unique symbol:adjusted priority
        # to efficiently utilize cores
        extract_tasks = optimize_pipeline_tasks(extract_tasks)

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
                        pool.imap(func, tasks, chunksize=1),
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
                    # Unlink merged csv
                    Path(options['output']).unlink(missing_ok=True)

        if not options['keep_temp']:
            # this is data/temp/builder/csv/uuid/temp
            # we need remove uuid directory
            adjust_dir = Path(f"{options['output_dir']}").parent / "adjust"
            locks_dir = Path(f"{options['output_dir']}").parent / "locks"
            if options['partition']:
                if adjust_dir.exists():
                    import shutil
                    print(f"Final cleanup of directory {adjust_dir}")
                    shutil.rmtree(adjust_dir)
                    shutil.rmtree(locks_dir)                     
            else:
                import shutil
                print("Final cleanup of directory "+str(Path(options['output_dir']).parent))
                shutil.rmtree(Path(options['output_dir']).parent)
            

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