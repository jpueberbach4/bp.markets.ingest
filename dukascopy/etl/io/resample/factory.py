#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        factory.py
 Author:      JP Ueberbach
 Created:     2026-01-07

 Description:
     Format-aware factory for resample and aggregation I/O handlers.

     This module provides a centralized factory (`ResampleIOFactory`) for
     creating readers, writers, and index handlers for both text (CSV) and
     binary formats. It abstracts format detection, file initialization, and
     ensures consistent interface usage across resampling and aggregation
     pipelines.

     Key classes and methods:
         - ResampleIOFactory: Factory class to obtain I/O handler instances.
             - get_reader(filepath, format_hint, **kwargs)
                 Returns a text or binary reader based on file or hint.
             - get_writer(filepath, format, **kwargs)
                 Returns a text or binary writer for writing OHLCV data.
             - get_index_handler(filepath, format, **kwargs)
                 Returns an index reader/writer for crash-safe offset tracking.
             - get_appropriate_extension(format)
                 Returns ".csv" or ".bin" for text or binary formats.
             - _detect_format(filepath)
                 Infers format from file extension or file content.

     Features:
         - Transparent support for both CSV and custom binary OHLCV formats.
         - Automatic format detection from file extension or content magic bytes.
         - Consistent, crash-safe interface for readers, writers, and indexes.
         - Supports optional keyword arguments for format-specific options
           such as encoding, fsync, batch size, etc.

 Usage:
     - Use `ResampleIOFactory.get_reader` to read OHLCV files incrementally.
     - Use `ResampleIOFactory.get_writer` to write OHLCV data safely.
     - Use `ResampleIOFactory.get_index_handler` to persist offsets for
       resumable processing.
     - Supports both text (CSV) and binary formats seamlessly.

 Requirements:
     - Python 3.8+
     - pandas

 Exceptions:
     - Inherited from underlying I/O classes:
         - ProcessingError
         - IndexCorruptionError
         - IndexValidationError
         - IndexWriteError
===============================================================================
"""

from pathlib import Path
from typing import Optional, Dict, Any

from etl.io.protocols import ResampleIOReader, ResampleIOWriter, ResampleIOIndexReaderWriter
from etl.io.resample.text import ResampleIOReaderText, ResampleIOWriterText, ResampleIOIndexReaderWriterText
from etl.io.resample.binary import ResampleIOReaderBinary, ResampleIOWriterBinary, ResampleIOIndexReaderWriterBinary
from etl.exceptions import *

class ResampleIOFactory:

    @staticmethod
    def get_reader(
        filepath: Path,
        format_hint: Optional[str] = None,
        **kwargs
    ) -> ResampleIOReader:
        if format_hint is None:
            format_hint = ResampleIOFactory._detect_format(filepath)
        
        if format_hint == 'binary':
            return ResampleIOReaderBinary(filepath, **kwargs)
        else:
            return ResampleIOReaderText(filepath, **kwargs)
    
    @staticmethod
    def get_writer(
        filepath: Path,
        format: str = 'text',
        **kwargs
    ) -> ResampleIOWriter:
        if format == 'binary':
            return ResampleIOWriterBinary(filepath, **kwargs)
        else:
            return ResampleIOWriterText(filepath, **kwargs)
    
    @staticmethod
    def get_index_handler(
        filepath: Path,
        format: str = 'text',
        **kwargs
    ) -> ResampleIOIndexReaderWriter:
        if format == 'binary':
            return ResampleIOIndexReaderWriterBinary(filepath, **kwargs)
        else:
            return ResampleIOIndexReaderWriterText(filepath, **kwargs)
    
    @staticmethod
    def _detect_format(filepath: Path) -> str:
        if filepath.suffix == '.bin':
            return 'binary'
        
        if filepath.exists():
            try:
                with open(filepath, 'rb') as f:
                    magic = f.read(8)
                    if magic == b'DUKASBIN':
                        return 'binary'
            except:
                pass
        
        return 'text'
    
    @staticmethod
    def get_appropriate_extension(format: str) -> str:
        return '.bin' if format == 'binary' else '.csv'