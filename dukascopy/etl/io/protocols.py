#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        protocols.py
 Author:      JP Ueberbach
 Created:     2026-01-07

 Description:
     Abstract base interfaces (protocols) for resample and aggregation I/O.

     This module defines abstract base classes (ABCs) for reading, writing,
     and index management of OHLCV data in both text (CSV) and binary formats.
     These interfaces provide a consistent, crash-safe contract for
     incremental and resumable processing in resampling and aggregation pipelines.

     Key classes:
         - EtlIO: Generic context-managed I/O interface supporting `with` statements.
         - ResampleIOReader: Abstract interface for batch reading, seeking,
           EOF detection, and offset tracking.
         - ResampleIOWriter: Abstract interface for batch writing, truncation,
           flushing, offset tracking, and finalization.
         - ResampleIOIndexReaderWriter: Abstract interface for reading and
           persisting input/output offsets for crash-safe incremental processing.

     Features:
         - Consistent interface for different storage formats (text, binary).
         - Supports context management for safe resource cleanup.
         - Provides the foundation for implementing crash-safe, incremental
           resampling or aggregation engines.
         - All concrete implementations must handle exceptions, file offsets,
           and end-of-file detection appropriately.

 Usage:
     - Subclass these ABCs to implement format-specific readers, writers,
       and index handlers.
     - Use in resampling or aggregation pipelines to enable:
         * Incremental reads and writes
         * Transactional file handling
         * Crash-safe offset tracking
     - Integrates with `ResampleIOFactory` to provide concrete implementations
       for text (CSV) and binary formats.

 Requirements:
     - Python 3.8+
     - pandas

 Exceptions:
     - Concrete subclasses may raise:
         - ProcessingError
         - IndexCorruptionError
         - IndexValidationError
         - IndexWriteError
===============================================================================
"""

from abc import ABC, abstractmethod
from typing import Tuple, Optional
import pandas as pd
from pathlib import Path


class EtlIO(ABC):
    
    @abstractmethod
    def close(self) -> None:
        pass
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

class ResampleIOReader(EtlIO):
    @abstractmethod
    def read_batch(self, batch_size: int) -> Tuple[pd.DataFrame, int]:
        pass
    
    @abstractmethod
    def seek(self, offset: int) -> None:
        pass
    
    @abstractmethod
    def tell(self) -> int:
        pass
    
    @abstractmethod
    def eof(self) -> bool:
        pass


class ResampleIOWriter(EtlIO):
    
    @abstractmethod
    def write_batch(self, df: pd.DataFrame, offset: Optional[int] = None) -> int:
        pass
    
    @abstractmethod
    def truncate(self, size: int) -> None:
        pass
    
    @abstractmethod
    def flush(self, fsync: bool = False) -> None:
        pass
    
    @abstractmethod
    def tell(self) -> int:
        pass
    
    @abstractmethod
    def finalize(self) -> Path:
        pass


class ResampleIOIndexReaderWriter(EtlIO):
    @abstractmethod
    def read(self) -> Tuple[int,int]:
        pass

    @abstractmethod
    def write(self, input_pos: int, output_pos: int) -> None:
        pass
     
