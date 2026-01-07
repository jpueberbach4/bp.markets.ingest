#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        binary.py
 Author:      JP Ueberbach
 Created:     2026-01-07

 Description:
     Binary-format, incremental OHLCV file I/O and aggregation engine.

     This module provides crash-safe, incremental reading, writing, and
     index-tracking for binary-formatted OHLCV data. It is designed to
     support batch resampling and aggregation pipelines with precise
     byte-offset or record-offset tracking for resumable processing.

     Key classes:
         - ResampleIOReaderBinary: Reads batches of binary records with
           offset tracking, providing EOF detection and random-access seeking.
         - ResampleIOWriterBinary: Writes batches of OHLCV records to binary
           files with optional fsync, truncation, flushing, and transactional
           safety.
         - ResampleIOIndexReaderWriterBinary: Manages persistent input/output
           offsets for crash-safe incremental processing of binary files.

     Features:
         - Batch reading and writing with support for resuming from a
           specific offset.
         - Optional fsync to guarantee durability of writes and index updates.
         - Transactional index updates using temporary files and atomic replace.
         - Integration with resampling pipelines or aggregation workflows.
         - Memory-mapped I/O for efficient reading of large datasets.

 Usage:
     - Imported and used by resampling or aggregation engines.
     - Supports multiprocessing or forked worker contexts.
     - Enables incremental appending and crash-safe recovery for OHLCV data.
     - Designed to be used via ResampleIOFactory to select text or binary I/O.

 Requirements:
     - Python 3.8+
     - numpy
     - pandas
     - mmap

 Exceptions:
     - ProcessingError: Raised for file corruption, empty files, or invalid operations.
     - IndexCorruptionError: Raised when an index file is malformed.
     - IndexValidationError: Raised when offsets are invalid.
     - IndexWriteError: Raised on failure to persist index to disk.
===============================================================================
"""
import os
import mmap
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Tuple, Optional

from etl.io.protocols import ResampleIOReader, ResampleIOWriter, ResampleIOIndexReaderWriter
from etl.exceptions import *

# TODO: magic and version in a binary header at beginning of file

class ResampleIOReaderBinary(ResampleIOReader):
    """
    Zero-copy binary reader using mmap and numpy memory views.

    Structure (64 bytes per record):
        - 8 bytes Timestamp (uint64)
        - 40 bytes OHLCV (5x float64)
        - 16 bytes padding
    """
    # Define the C-struct equivalent for numpy
    DTYPE = np.dtype([
        ('ts', '<u8'),           # Timestamp in milliseconds
        ('ohlcv', '<f8', (5,)),  # Open, High, Low, Close, Volume
        ('padding', '<u8', (2,)) # Padding to 64 bytes
    ])
 
    RECORD_SIZE = 64  # Fixed size of each record in bytes.
                      # Aligned to standard x86_64 CPU cache-line size.
                      # This ensures a single record never spans across two cache lines,
                      # minimizing memory latency and preventing split-load penalties.

    def __init__(self, filepath: Path, **kwargs):
        """
        Initialize a binary reader with memory-mapped access.

        Args:
            filepath (Path): Path to the binary OHLCV file.
            **kwargs: Placeholder for future extensions.
        """
        self.filepath = filepath
        self.file_handle = None
        self.mm = None
        self.data_view = None
        self._pos = 0  # Current byte offset
        self._open()

    def _open(self) -> None:
        """
        Open the binary file and memory-map it for zero-copy reading.

        Raises:
            ProcessingError: If the file is empty or mapping fails.
        """
        try:
            self.file_handle = open(self.filepath, 'rb')
            size = os.path.getsize(self.filepath)
            if size == 0:
                raise ProcessingError(f"Empty binary file: {self.filepath}")

            # Map the file into memory
            self.mm = mmap.mmap(self.file_handle.fileno(), 0, access=mmap.ACCESS_READ)
            # Create a zero-copy numpy view of the memory map
            self.data_view = np.frombuffer(self.mm, dtype=self.DTYPE)
        except Exception as e:
            self.close()
            raise ProcessingError(f"Failed to map binary file {self.filepath}: {e}")

    def read_batch(self, batch_size: int) -> pd.DataFrame:
        """
        Read a batch of records as a DataFrame.

        Args:
            batch_size (int): Maximum number of records to read.

        Returns:
            pd.DataFrame: DataFrame with columns ['open', 'high', 'low', 'close', 'volume'],
            indexed by 'time', and an additional 'offset' column in bytes.
        """
        start_idx = self._pos // self.RECORD_SIZE
        end_idx = min(start_idx + batch_size, len(self.data_view))

        if start_idx >= end_idx:
            return pd.DataFrame()

        # Zero-copy slicing of the memory view
        batch = self.data_view[start_idx:end_idx]

        # Vectorized DataFrame creation
        df = pd.DataFrame(
            batch['ohlcv'],
            columns=['open', 'high', 'low', 'close', 'volume'],
            index=pd.to_datetime(batch['ts'], unit='ms')
        )
        df.index.name = 'time'

        # Add byte offsets for each row (required for incremental resample logic)
        df['offset'] = np.arange(start_idx, end_idx) * self.RECORD_SIZE

        self._pos = end_idx * self.RECORD_SIZE
        return df

    def seek(self, offset: int) -> None:
        """
        Move the reader to a specific byte offset.

        Args:
            offset (int): Byte offset in the file.
        """
        self._pos = offset

    def tell(self) -> int:
        """
        Return the current byte offset.

        Returns:
            int: Current byte offset in the file.
        """
        return self._pos

    def eof(self) -> bool:
        """
        Check if end-of-file is reached.

        Returns:
            bool: True if the current position is at or beyond EOF.
        """
        return self._pos >= len(self.mm)

    def close(self) -> None:
        """
        Close the memory map and file handle.
        """
        if self.mm: self.mm.close()
        if self.file_handle: self.file_handle.close()


class ResampleIOWriterBinary(ResampleIOWriter):
    """
    High-performance binary writer using pre-allocated record buffers.
    """
    def __init__(self, filepath: Path, fsync: bool = False, **kwargs):
        """
        Initialize a binary writer.

        Args:
            filepath (Path): Path to write OHLCV binary data.
            fsync (bool, optional): Force flush to disk on writes.
            **kwargs: Placeholder for future extensions.
        """
        self.filepath = filepath
        self.fsync = fsync
        self.file = None
        self._initialize()

    def _initialize(self) -> None:
        """
        Prepare the file for writing, creating parent directories as needed.
        """
        if not self.filepath.exists():
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
            mode = 'wb+'
        else:
            mode = 'rb+'
        self.file = open(self.filepath, mode)

    def write_batch(self, df: pd.DataFrame, offset: Optional[int] = None) -> int:
        """
        Write a batch of OHLCV records to the binary file.

        Args:
            df (pd.DataFrame): DataFrame with OHLCV data indexed by time.
            offset (Optional[int]): Byte offset at which to write. Appends if None.

        Returns:
            int: File position after writing the batch.
        """
        if offset is not None:
            self.file.seek(offset)

        count = len(df)
        buf = np.zeros(count, dtype=ResampleIOReaderBinary.DTYPE)
        buf['ts'] = df.index.values.astype('datetime64[ms]').astype('uint64')
        buf['ohlcv'] = df[['open', 'high', 'low', 'close', 'volume']].values

        # Write all records at once
        self.file.write(buf.tobytes())
        return self.file.tell()

    def truncate(self, size: int) -> None:
        """
        Truncate the file to a specific size.

        Args:
            size (int): New file size in bytes.
        """
        self.file.truncate(size)

    def flush(self, fsync: bool = False) -> None:
        """
        Flush the file buffer to disk.

        Args:
            fsync (bool): Whether to force a full disk sync.
        """
        self.file.flush()
        if fsync or self.fsync:
            os.fsync(self.file.fileno())

    def tell(self) -> int:
        """
        Return the current file write position.

        Returns:
            int: Current byte offset.
        """
        return self.file.tell()

    def finalize(self) -> Path:
        """
        Flush, close the file, and return its path.

        Returns:
            Path: Filepath of the finalized file.
        """
        self.flush(fsync=True)
        self.close()
        return self.filepath

    def close(self) -> None:
        """
        Close the file handle.
        """
        if self.file:
            self.file.close()
            self.file = None


class ResampleIOIndexReaderWriterBinary(ResampleIOIndexReaderWriter):
    # New 24-byte structure
    STRUCT = np.dtype([
        ('last_date', '<i4'), 
        ('padding', '<u4'), 
        ('in_pos', '<u8'), 
        ('out_pos', '<u8')
    ])
    # Legacy 16-byte structure for migration
    LEGACY_STRUCT = np.dtype([('in_pos', '<u8'), ('out_pos', '<u8')])

    def __init__(self, index_path: Path, fsync: bool = False, **kwargs):
        self.index_path = index_path
        self.fsync = fsync

    def read(self) -> Tuple[int, int, int]:
        if not self.index_path.exists():
            self.write(0, 0, 19700101)
            return 19700101, 0, 0

        file_size = self.index_path.stat().st_size

        try:
            # Migration Logic: If size is 16 bytes, read as legacy
            if file_size == 16:
                data = np.fromfile(self.index_path, dtype=self.LEGACY_STRUCT, count=1)
                # Return epoch date for legacy files to force a safety check
                return 19700101, int(data['in_pos'][0]), int(data['out_pos'][0])
            
            # Standard Path: Read new 24-byte structure
            data = np.fromfile(self.index_path, dtype=self.STRUCT, count=1)
            return (
                int(data['last_date'][0]),
                int(data['in_pos'][0]),
                int(data['out_pos'][0])
            )
        except Exception as e:
            raise IndexCorruptionError(f"Binary index corrupted: {self.index_path}") from e

    def write(self, input_pos: int, output_pos: int, dt: int = 19700101) -> None:
        temp_path = self.index_path.with_suffix(".tmp")
        data = np.array([(dt, 0, input_pos, output_pos)], dtype=self.STRUCT)

        with open(temp_path, 'wb') as f:
            f.write(data.tobytes())
            f.flush()
            if self.fsync:
                os.fsync(f.fileno())
        os.replace(temp_path, self.index_path)

    def close(self) -> None:
        pass