from pathlib import Path
from typing import Optional, Dict, Any

from etl.io.protocols import ResampleIOReader, ResampleIOWriter, ResampleIOIndexReaderWriter
from etl.io.resample.text import ResampleIOReaderText, ResampleIOWriterText, ResampleIOIndexReaderWriterText
from etl.io.resample.binary import ResampleIOReaderBinary, ResampleIOWriterBinary, ResampleIOIndexReaderWriterBinary

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