#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        merge.py
 Author:      JP Ueberbach
 Created:     2025-12-13
 Description: Module to handle merging of temporary Dukascopy output files (CSV 
              or Parquet) into a single consolidated output file.

              This module supports:
              - Merging partitioned Parquet datasets or multiple CSV files.
              - Ordering by timestamp.
              - Applying compression options.
              - Optional cleanup of temporary directories after merge.

 Requirements:
     - Python 3.8+
     - duckdb

 License:
     MIT License
===============================================================================
"""
import shutil
from pathlib import Path
import duckdb

def merge_output_files(
    input_dir: Path,
    output_file: str,
    output_type: str,
    compression: str,
    cleanup: bool
) -> int:
    """
    Merge multiple temporary output files into a single consolidated file.

    Parameters:
    -----------
    input_dir : Path
        Directory containing temporary CSV or Parquet files to merge.
    output_file : str
        Path for the final consolidated output file.
    output_type : str
        Output format: 'CSV' or 'PARQUET'.
    compression : str
        Compression codec to use for the output file.
    cleanup : bool
        Whether to remove the input directory after successful merge.

    Returns:
    --------
    int
        Number of input files processed/merged.

    Raises:
    -------
    ValueError
        If an unsupported output_type is provided.
    Exception
        For any DuckDB execution errors.
    """
    output_type = output_type.upper()
    compression = compression.upper()

    # Configure input file pattern, read function, and DuckDB COPY format options
    if output_type == "PARQUET":
        input_pattern = str(input_dir / "**" / "*.parquet")
        read_func = "read_parquet"
        format_options = f"""
            FORMAT PARQUET,
            COMPRESSION '{compression}',
            ROW_GROUP_SIZE 1000000
        """
        read_options = ", union_by_name=true"  # Ensure consistent column names across partitions
    elif output_type == "CSV":
        input_pattern = str(input_dir / "**" / "*.csv")
        read_func = "read_csv_auto"
        format_options = f"""
            FORMAT CSV,
            HEADER true,
            DELIMITER ',',
            COMPRESSION '{compression}'
        """
        read_options = ""  # CSV union_by_name not required
    else:
        raise ValueError(f"Unsupported output type for merging: {output_type}")

    # Gather list of input files
    input_files = list(input_dir.glob(f"**/*.{output_type.lower()}"))
    if not input_files:
        print(f"Warning: No temporary {output_type} files found in {input_dir}. Nothing to merge.")
        return 0

    # Connect to an in-memory DuckDB instance for merging
    con = duckdb.connect(database=":memory:")

    try:
        # Construct and execute the DuckDB COPY command
        merge_query = f"""
            COPY (
                SELECT * FROM {read_func}('{input_pattern}'{read_options})
                ORDER BY time ASC
            )
            TO '{output_file}'
            (
                {format_options}
            );
        """
        con.execute(merge_query)
        return len(input_files)

    except Exception as e:
        print(f"Critical error during consolidation: {e}")
        raise

    finally:
        # Optionally clean up the temporary input directory
        if cleanup:
            try:
                shutil.rmtree(input_dir)
                print(f"Cleaned up temporary directory: {input_dir}")
            except OSError as e:
                print(f"Error during cleanup of {input_dir}: {e}")

        # Close DuckDB connection
        con.close()
