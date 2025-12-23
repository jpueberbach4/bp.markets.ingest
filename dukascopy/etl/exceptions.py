
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 File:        exceptions.py
 Author:      JP Ueberbach
 Created:     2025-12-16
 Description: Module containing all the custom exceptions raised by the various
              ETL workers.

 Requirements:
     - Python 3.8+

 License:
     MIT License
===============================================================================
"""
class EtlError(Exception):
    """Base exception for all resampling errors."""
    pass

class DataNotFoundError(EtlError):
    """Raised when source CSVs or base timeframes are missing."""
    pass

class IndexCorruptionError(EtlError):
    """Raised when .idx files are unreadable or logically inconsistent."""
    pass

class ProcessingError(EtlError):
    """Raised during Pandas resampling or post-processing merges."""
    pass

class IndexWriteError(EtlError):
    """Raised when the index cannot be persisted to disk."""
    pass

class IndexValidationError(EtlError):
    """Raised when the offsets being written are logically invalid."""
    pass

class BatchError(EtlError):
    """Base for batch preparation failures."""
    pass

class SessionResolutionError(BatchError):
    """Raised when the tracker cannot map a timestamp to a session."""
    pass

class ResampleLogicError(ProcessingError):
    """Raised when the resampling math produces inconsistent results."""
    pass

class EmptyBatchError(ProcessingError):
    """Raised when a batch contains no valid data after filtering."""
    pass

class PostProcessingError(ProcessingError):
    """Raised when post processing fails."""
    pass

class WorkerError(EtlError):
    """Base for worker-level orchestration failures."""
    pass

class DependencyError(WorkerError):
    """Raised when a timeframe cannot be processed because its source is broken."""
    pass

class TransactionError(WorkerError):
    """Raised when the write-sync-index cycle fails."""
    pass

class ForkProcessError(WorkerError):
    """Raised when a parallelized worker process fails at the top level."""
    pass

class TransformLogicError(ProcessingError):
    """Raised when the resampling math produces inconsistent results."""
    pass

class DataValidationError(ProcessingError):
    """Raised when the data validation fails."""
    pass
