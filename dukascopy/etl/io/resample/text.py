#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        text.py
 Author:      JP Ueberbach
 Created:     2026-01-07

 Description:
     Text-based, incremental OHLCV file I/O and aggregation engine.

     This module provides crash-safe, incremental reading, writing, and
     index-tracking for CSV-formatted OHLCV data. It is designed to support
     batch resampling and aggregation pipelines with precise byte-offset
     tracking for resumable processing.

     Key classes:
         - ResampleIOReaderText: Reads batches of CSV rows with byte-offset
           tracking, providing EOF detection and random-access seeking.
         - ResampleIOWriterText: Writes batches of OHLCV data to CSV with
           optional fsync, truncation, flushing, and transactional safety.
         - ResampleIOIndexReaderWriterText: Manages persistent input/output
           offsets for crash-safe incremental processing.

     Features:
         - Batch reading and writing with support for resuming from a
           specific byte offset.
         - Automatic header parsing for input CSV files.
         - Optional fsync to guarantee durability of writes and index updates.
         - Transactional index updates using temporary files and atomic replace.
         - Integration with resampling pipelines or aggregation workflows.

 Usage:
     - Imported and used by resampling or aggregation engines.
     - Supports multiprocessing or forked worker contexts.
     - Enables incremental appending and crash-safe recovery for OHLCV data.

 Requirements:
     - Python 3.8+
     - pandas

 Exceptions:
     - ProcessingError: Raised for file corruption, empty files, or invalid operations.
     - IndexCorruptionError: Raised when an index file is malformed.
     - IndexValidationError: Raised when offsets are invalid.
     - IndexWriteError: Raised on failure to persist index to disk.
===============================================================================
"""
import os
import pandas as pd
from pathlib import Path
from typing import Tuple, Optional
from io import StringIO
import io

from etl.io.protocols import ResampleIOReader, ResampleIOWriter, ResampleIOIndexReaderWriter
from etl.exceptions import *

class ResampleIOReaderText(ResampleIOReader):
    
    def __init__(self, filepath: Path, encoding: str = 'utf-8', **kwargs):
        """Initialize a file reader with optional encoding and automatic opening.

        This constructor sets up the file path, encoding, and internal state for
        reading. The file is opened immediately upon initialization. Additional
        keyword arguments can be used for subclass-specific configurations.

        Args:
            filepath (Path): Path to the file to be read.
            encoding (str, optional): Character encoding for reading the file.
                Defaults to 'utf-8'.
            **kwargs: Additional keyword arguments for subclass-specific options.

        Attributes:
            filepath (Path): Path to the file being read.
            encoding (str): Character encoding used for reading the file.
            file: File object, opened during initialization.
            header: Parsed header information, if applicable.
            byte_offset (int): Current read position in bytes within the file.
        """
        self.filepath = filepath
        self.encoding = encoding
        self.file = None
        self.header = None
        self.byte_offset = 0
        self._open()
    
    def _open(self) -> None:
        """Open the file in binary mode, read the header, and set the initial byte offset.

        This method opens the file specified by `self.filepath` in binary mode,
        reads the first line as the header, decodes it using the specified encoding,
        and updates the internal byte offset to the position after the header.

        Raises:
            ProcessingError: If the file is empty or the header cannot be read.
        """
        self.file = open(self.filepath, 'rb')
        first_line = self.file.readline()
        if not first_line:
            raise ProcessingError(f"Empty CSV file: {self.filepath}")

        self.header = first_line.decode(self.encoding).strip()
        self.byte_offset = self.file.tell()
    
    def read_batch(self, batch_size: int) -> pd.DataFrame:
        """Read a batch of rows from the file and return as a DataFrame.

        This method reads up to `batch_size` lines from the current file position,
        appends an `offset` column indicating the byte position of each row in the
        file, and returns the data as a Pandas DataFrame indexed by the `time` column.
        The file is read in binary mode, and lines are decoded using UTF-8.

        Args:
            batch_size (int): The maximum number of rows to read in this batch.

        Returns:
            pd.DataFrame: A DataFrame containing the batch of rows, with columns
            `open`, `high`, `low`, `close`, `volume`, and `offset`, indexed by `time`.

        Raises:
            RuntimeError: If an unexpected error occurs during file reading or
                DataFrame construction.
        """
        header = "time,open,high,low,close,volume\n"
        sio = StringIO()
        try:
            sio.write(f"{header.strip()},offset\n")
            self.byte_offset = offset_before = self.file.tell()
            for _ in range(batch_size):
                line_bytes = self.file.readline()
                if not line_bytes:
                    break

                line = line_bytes.decode('utf-8').strip()
                sio.write(f"{line.strip()},{self.byte_offset}\n")
                self.byte_offset += len(line_bytes) 
            
            sio.seek(0)
            
            df = pd.read_csv(
                sio,
                parse_dates=["time"],
                index_col="time",
                date_format="%Y-%m-%d %H:%M:%S",
                low_memory=False,
                sep=',',
            )
            sio.close()

            return df
        except Exception as e:
            raise RuntimeError(f"Unexpected system failure during batching: {e}") from e
    
    def seek(self, offset: int) -> None:
        """Move the file read pointer to a specific byte offset.

        This method updates the file's current read position and synchronizes
        the internal `byte_offset` tracker to allow incremental or resumed reading.

        Args:
            offset (int): The byte position in the file to seek to.
        """
        self.file.seek(offset)
        self.byte_offset = offset
    
    def tell(self) -> int:
        """Return the current byte offset in the file.

        This method provides the current read position within the file, which
        can be used to resume reading or track progress in incremental processing.

        Returns:
            int: The current byte offset in the file.
        """
        return self.byte_offset
    
    def eof(self) -> bool:
        """Check if the file pointer has reached the end of the file.

        This method compares the current byte offset with the total file size
        to determine whether all content has been read. The file pointer is
        restored to its original position after the check.

        Returns:
            bool: True if the file pointer is at or beyond the end of the file,
                False otherwise.
        """
        current = self.file.tell()
        self.file.seek(0, 2)  # Seek to end
        end = self.file.tell()
        self.file.seek(current)
        return current >= end
    
    def close(self) -> None:
        """Close the open file and release associated resources.

        This method safely closes the file if it is currently open and
        sets the internal file reference to None. After calling this method,
        the file object cannot be used for further reading unless reopened.
        """
        if self.file:
            self.file.close()
            self.file = None


class ResampleIOWriterText(ResampleIOWriter):
    
    def __init__(self, filepath: Path, fsync: bool = False, encoding: str = 'utf-8'):
        """Initialize a file writer with optional fsync and encoding settings.

        This constructor sets up the file path, encoding, and whether
        writes should be flushed to disk using fsync. It also initializes
        internal state for tracking bytes written and opens the file
        immediately via `_initialize()`.

        Args:
            filepath (Path): Path to the file to be written.
            fsync (bool, optional): Whether to flush writes to disk for
                durability after each write. Defaults to False.
            encoding (str, optional): Character encoding used for writing
                text data. Defaults to 'utf-8'.

        Attributes:
            filepath (Path): Path to the file being written.
            fsync (bool): Flag indicating if writes are synchronized to disk.
            encoding (str): Character encoding used for writing.
            file: Open file object.
            bytes_written (int): Total number of bytes written to the file.
        """
        self.filepath = filepath
        self.fsync = fsync
        self.encoding = encoding
        self.file = None
        self.bytes_written = 0
        self._initialize()
    
    def _initialize(self) -> None:
        """Prepare the output file for writing and initialize internal state.

        This method ensures that the target file and its parent directories exist,
        opens the file in read-write mode, and writes a CSV header if the file
        is newly created. For existing files, it reads past the header to maintain
        the current write position. It also updates the internal byte counter
        if a header is written.

        Raises:
            OSError: If the file or directories cannot be created or opened.
        """
        new_file = False
        if not Path(self.filepath).exists():
            Path(self.filepath).parent.mkdir(parents=True, exist_ok=True)
            Path(self.filepath).touch()
            new_file = True
        
        self.file = open(self.filepath, 'r+', encoding=self.encoding, newline='')

        if new_file:
            self.bytes_written += self.file.write("time,open,high,low,close,volume\n")
        else:
            self.file.readline()

    def write_batch(self, df: pd.DataFrame, offset: Optional[int] = None) -> int:
        """Write a batch of DataFrame rows to the file as CSV.

        This method serializes the DataFrame to CSV format without headers,
        using the index as the `time` column. If an `offset` is provided,
        writing will begin at that byte position in the file. The total number
        of bytes written is tracked and returned.

        Args:
            df (pd.DataFrame): DataFrame containing OHLCV data to write.
                The index must be datetime-like and represents the timestamp
                of each row.
            offset (Optional[int], optional): Byte offset in the file where
                writing should begin. Defaults to None, which appends to the
                current file position.

        Returns:
            int: Total number of bytes written to the file, including any
                previous writes.

        Raises:
            OSError: If the file cannot be written to at the specified offset.
        """
        df.index = df.index.strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        csv_str = df.to_csv(index=True, header=False)
        if offset:
            self.file.seek(offset)

        self.bytes_written += self.file.write(csv_str)
        return self.bytes_written
    
    def truncate(self, size: int) -> None:
        """Truncate the file to a specified byte size.

        This method shortens or resets the file to the given size in bytes.
        It is typically used to roll back partial writes or to enforce
        transactional output behavior.

        Args:
            size (int): The byte size to truncate the file to. Must be non-negative.

        Raises:
            ValueError: If `size` is negative.
            OSError: If the truncation operation fails at the filesystem level.
        """
        if size < 0:
            raise ValueError("Truncation size cannot be negative")

        self.file.truncate(size)
    
    def flush(self, fsync: bool = False) -> None:
        """Flush buffered file data to disk, optionally forcing an fsync.

        This method flushes the internal write buffer to ensure that all
        written data is pushed to the operating system. If `fsync` is True
        or the writer was initialized with `fsync=True`, the method also
        forces a filesystem-level sync to guarantee data durability.

        Args:
            fsync (bool, optional): Whether to force a full disk sync after
                flushing. Defaults to False.

        Raises:
            OSError: If flushing or fsync fails at the OS level.
        """
        if self.file:
            self.file.flush()
            if fsync or self.fsync:
                os.fsync(self.file.fileno())
    
    def tell(self) -> int:
        """Return the current byte offset in the file.

        This method retrieves the file's current write position, which can
        be used for resuming writes, tracking progress, or performing
        transactional operations.

        Returns:
            int: The current byte offset in the file.
        """
        return self.file.tell()
    
    def finalize(self) -> Path:
        """Flush, close the file, and return its path.

        This method ensures that all buffered data is written to disk with
        an fsync, closes the file, and returns the path of the finalized
        file. It is intended to be called when all writing operations are
        complete.

        Returns:
            Path: The path to the finalized file.

        Raises:
            ProcessingError: If the file has not been initialized or is already closed.
            OSError: If flushing or closing the file fails.
        """
        if not self.file:
            raise ProcessingError("Writer not initialized")
        
        self.flush(fsync=True)
        self.file.close()
        
        return self.filepath
    
    def close(self) -> None:
        """Close the open file and release resources.

        This method safely closes the file if it is currently open and
        sets the internal file reference to None. After calling this method,
        the file object cannot be used for further writing unless reopened.

        Raises:
            OSError: If closing the file fails at the operating system level.
        """
        if self.file:
            self.file.close()
            self.file = None


class ResampleIOIndexReaderWriterText(ResampleIOIndexReaderWriter):
    def __init__(self, index_path: Path, fsync: bool = False):
        """Initialize an index handler for tracking input/output positions.

        This constructor sets up the file path for the index and whether
        writes should be synchronized to disk using fsync. The index is
        used to persist the current read/write offsets for crash-safe
        incremental processing.

        Args:
            index_path (Path): Path to the index file used to store offsets.
            fsync (bool, optional): Whether to flush writes to disk for
                durability after each update. Defaults to False.

        Attributes:
            index_path (Path): Path to the index file.
            fsync (bool): Flag indicating if writes should be fsynced.
        """
        self.index_path = index_path
        self.fsync = fsync
    
    def read(self) -> Tuple[int, int]:
        """Read input and output offsets from the index file.

        This method retrieves the last persisted input and output positions
        from the index file. If the index file does not exist, it is
        automatically initialized with zeros. The method validates that
        the file contains exactly two numeric lines and raises an exception
        if corruption is detected.

        Returns:
            Tuple[int, int]: A tuple containing the input offset and
            output offset.

        Raises:
            IndexCorruptionError: If the index file is incomplete, contains
                non-numeric values, or is otherwise corrupted.
        """
        try:
            if not self.index_path.exists():
                self.write(0, 0)
                return 0, 0
            
            with open(self.index_path, "r") as f:
                lines = f.readlines()[:2]
            
            if len(lines) < 2:
                raise IndexCorruptionError(f"Incomplete index at {self.index_path}")
            
            return int(lines[0].strip()), int(lines[1].strip())
            
        except (ValueError, IndexError) as e:
            raise IndexCorruptionError(f"Corrupt index at {self.index_path}: {e}")
    
    def write(self, input_pos: int, output_pos: int) -> None:
        """Persist input and output offsets to the index file.

        This method writes the given input and output positions to a temporary
        file and atomically replaces the existing index file to ensure
        crash-safe updates. Optionally, it can force a filesystem-level
        flush (fsync) for durability.

        Args:
            input_pos (int): The current input offset to persist.
            output_pos (int): The current output offset to persist.

        Raises:
            IndexValidationError: If either offset is negative.
            IndexWriteError: If the index cannot be written to disk due
                to an OS-level failure.
        """
        if input_pos < 0 or output_pos < 0:
            raise IndexValidationError(
                f"Invalid offsets: IN={input_pos}, OUT={output_pos}"
            )
        
        try:
            self.index_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self.index_path.with_suffix(".tmp")
            
            with open(temp_path, "w") as f:
                f.write(f"{input_pos}\n{output_pos}")
                f.flush()
                if self.fsync:
                    os.fsync(f.fileno())
            
            os.replace(temp_path, self.index_path)
            
        except OSError as e:
            raise IndexWriteError(f"Failed to persist index: {e}")
    
    def close(self) -> None:
        """Close the index handler.

        This method is a placeholder for compatibility with the interface.
        The text-based index does not require explicit closure because files
        are opened and closed per operation.

        Note:
            No action is performed in this implementation.
        """
        pass    