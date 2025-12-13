#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        args.py
 Author:      JP Ueberbach
 Created:     2025-12-13
 Description: Command-line argument parsing for Dukascopy batch extraction 
              utility.

              Provides:
              - parse_args: Parse and validate CLI options for extraction, 
                listing, and export.

              Features:
              - Select symbols/timeframes with optional modifiers
              - List available datasets
              - Filter by date range
              - Configure output type, partitioning, compression, and MT4 export
              - Supports dry-run mode for testing

 Requirements:
     - Python 3.8+

 License:
     MIT License
===============================================================================
"""
import argparse
import sys
import uuid
from datetime import datetime
from helper import BuilderConfig, CustomArgumentParser, resolve_selections, get_available_data_from_fs
# Assuming config is correctly imported
# from config.app_config import BuilderConfig

# Default date range for extraction
DEFAULT_AFTER = "1970-01-01 00:00:00"
DEFAULT_UNTIL = "3000-01-01 00:00:00"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

def parse_args(config: BuilderConfig):
    """
    Parse and validate command-line arguments for Dukascopy extraction.

    Parameters:
    -----------
    config : BuilderConfig
        Configuration object containing data paths and other settings.

    Returns:
    --------
    dict
        Dictionary of validated options.
    """

    parser = CustomArgumentParser(
        description="Batch extraction utility for symbol/timeframe datasets.",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    # Mutually exclusive group: select datasets or list available
    command_group = parser.add_mutually_exclusive_group(required=True)
    command_group.add_argument(
        "--select",
        action="append",
        metavar="SYMBOL/TF1,TF2:modifier,...",
        help="Defines how symbols and timeframes are selected for extraction.",
    )
    command_group.add_argument(
        "--list",
        action="store_true",
        help="Dump out all available symbol/timeframe pairs and exit.",
    )

    # Date range filters
    parser.add_argument(
        "--after", 
        type=str, 
        default=DEFAULT_AFTER,
        help=f"Start date/time (inclusive). Format: YYYY-MM-DD HH:MM:SS (Default: {DEFAULT_AFTER})"
    )
    parser.add_argument(
        "--until", 
        type=str, 
        default=DEFAULT_UNTIL,
        help=f"End date/time (exclusive). Format: YYYY-MM-DD HH:MM:SS (Default: {DEFAULT_UNTIL})"
    )

    # Output configuration
    output_group = parser.add_argument_group("Output Configuration (Required for Extraction Mode)")
    output_group.add_argument(
        "--output", 
        type=str, 
        metavar="FILE_PATH",
        help="Write a single merged output file."
    )
    output_group.add_argument(
        "--output_dir", 
        type=str, 
        metavar="DIR_PATH",
        help="Write a partitioned dataset."
    )

    # Mutually exclusive output type
    type_group = parser.add_mutually_exclusive_group()
    type_group.add_argument(
        "--csv", 
        action="store_const", 
        const="csv", 
        dest="output_type",
        help="Write as CSV."
    )
    type_group.add_argument(
        "--parquet", 
        action="store_const", 
        const="parquet", 
        dest="output_type",
        help="Write as Parquet (default)."
    )

    # Compression options
    parser.add_argument(
        "--compression",
        type=str,
        default="zstd",
        choices=["snappy", "gzip", "brotli", "zstd", "lz4", "none"],
        help="Compression codec for Parquet output.",
    )

    # Other flags
    parser.add_argument(
        "--mt4", 
        action="store_true",
        help="Splits merged CSV into files compatible with MT4."
    )
    parser.add_argument(
        "--force", 
        action="store_true",
        help="Allow patterns that match no files."
    )
    parser.add_argument(
        "--dry-run", 
        action="store_true",
        help="Parse/resolve arguments only; do not run extraction."
    )
    parser.add_argument(
        "--partition", 
        action="store_true",
        help="Enable Hive-style partitioned output (requires --output_dir)."
    )
    parser.add_argument(
        "--keep-temp", 
        action="store_true",
        help="Retain intermediate files."
    )

    # Parse CLI arguments
    args = parser.parse_args()

    # ... (Validation logic remains unchanged) ...

    # Validate date format
    try:
        dt_after = datetime.strptime(args.after, DATE_FORMAT) if args.after else None
        dt_until = datetime.strptime(args.until, DATE_FORMAT) if args.until else None
    except ValueError:
        parser.error(f"Invalid date format. Expected: {DATE_FORMAT}")

    if dt_after and dt_until and dt_after >= dt_until:
        parser.error("--after must be strictly earlier than --until")

    # Default output type
    args.output_type = args.output_type or "parquet"

    # Validate compression based on output type
    compression_choices = {
        "parquet": ["snappy", "gzip", "brotli", "zstd", "lz4", "none", "uncompressed"],
        "csv": ["none", "uncompressed", "gzip", "zstd"],
    }
    if args.compression not in compression_choices.get(args.output_type, ["none"]):
        parser.error(
            f"Compression '{args.compression}' is not suitable for output type '{args.output_type}'. "
            f"Valid options are: {', '.join(compression_choices.get(args.output_type, ['none']))}"
        )

    # Validate required output options for extraction mode
    if args.select and not (args.output or args.output_dir):
        parser.error("--select requires --output_dir or --output")

    if args.partition and not args.output_dir:
        parser.error("--partition requires --output_dir")

    if args.output_dir and not args.partition:
        parser.error("--output_dir requires --partition")

    if args.partition and args.mt4:
        parser.error("--mt4 incompatible with --partition")

    if args.output_type == "parquet" and args.mt4:
        parser.error("--parquet incompatible with --mt4")

    # Discover available datasets from filesystem
    # NOTE: Assuming get_available_data_from_fs is available in scope (e.g., imported from helper)
    all_available_data = get_available_data_from_fs(config)

    # List available symbols and timeframes
    if args.list:
        symbols = {}
        for symbol, timeframe, _ in all_available_data:
            symbols.setdefault(symbol, []).append(timeframe)

        print("\n--- Available Symbols and Timeframes" + "-" * 43)
        for symbol in sorted(symbols):
            print(f"{symbol:<20} timeframes: [{', '.join(sorted(symbols[symbol]))}]")
        print("-" * 80)
        sys.exit(0)

    # Resolve selections to actual CSV files
    # NOTE: Assuming resolve_selections is available in scope (e.g., imported from helper)
    final_selections, _ = resolve_selections(
        parser=parser,
        select_args=args.select,
        all_available_data=all_available_data,
        force=args.force,
    )

    # Normalize compression for CSV or 'none'
    if args.compression == "none" or args.output_type == "csv":
        args.compression = "uncompressed"

    # Generate temp directory if not partitioned
    if not args.partition:
        # NOTE: Using config.paths.temp, adjust if necessary
        args.output_dir = f"{config.paths.temp}/{args.output_type}/{uuid.uuid4()}"

    # Return dictionary of validated options
    return {
        "select_data": sorted(final_selections),
        "partition": args.partition,
        "output_dir": args.output_dir,
        "output_type": args.output_type,
        "dry_run": args.dry_run,
        "force": args.force,
        "keep_temp": args.keep_temp,
        "after": args.after,
        "until": args.until,
        "output": args.output,
        "compression": args.compression,
        "mt4": args.mt4,
    }