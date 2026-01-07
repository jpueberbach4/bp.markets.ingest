import os
import pandas as pd
from pathlib import Path
from typing import Tuple, Optional
import io

from etl.io.protocols import ResampleIOReader, ResampleIOWriter
from etl.exceptions import ProcessingError

class ResampleIOReaderText(ResampleIOReader):
    
    def __init__(self, filepath: Path, encoding: str = 'utf-8'):
        self.filepath = filepath
        self.encoding = encoding
        self.file = None
        self.header = None
        self.byte_offset = 0
        self._open()
    
    def _open(self) -> None:
        self.file = open(self.filepath, 'rb')
        first_line = self.file.readline()
        if not first_line:
            raise ProcessingError(f"Empty CSV file: {self.filepath}")
        self.header = first_line.decode(self.encoding).strip()
        self.byte_offset = self.file.tell()
    
    def read_batch(self, offset: int, batch_size: int) -> pd.DataFrame:
        sio = StringIO()
        try:
            sio.write(f"{header.strip()},offset\n")
            offset_before = self.file.tell()
            for _ in range(batch_size):
                line_bytes = self.file.readline()
                if not line_bytes:
                    break

                line = line_bytes.decode('utf-8').strip()
                sio.write(f"{line.strip()},{offset_before}\n")
                offset_before += len(line_bytes)
            
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
        
        return df, self.byte_offset
    
    def seek(self, offset: int) -> None:
        self.file.seek(offset)
        self.byte_offset = offset
    
    def tell(self) -> int:
        return self.byte_offset
    
    def eof(self) -> bool:
        current = self.file.tell()
        self.file.seek(0, 2)  # Seek to end
        end = self.file.tell()
        self.file.seek(current)
        return current >= end
    
    def close(self) -> None:
        if self.file:
            self.file.close()
            self.file = None


class ResampleIOWriterText(ResampleIOWriter):
    
    def __init__(self, filepath: Path, fsync: bool = False, encoding: str = 'utf-8'):
        self.filepath = filepath
        self.fsync = fsync
        self.encoding = encoding
        self.file = None
        self.bytes_written = 0
        self._initialize()
    
    def _initialize(self) -> None:
        new_file = False
        if not Path(self.filepath).exists():
            Path(self.filepath).touch()
            new_file = True
        
        self.file = open(self.filepath, 'r+', encoding=self.encoding, newline='')

        if new_file:
            self.bytes_written += self.file.write("time,open,high,low,close,volume\n")

    def write_batch(self, df: pd.DataFrame, offset: Optional[int] = None) -> int:
        csv_str = df.to_csv(index=True, header=False)
        self.bytes_written += self.file.write(csv_str)
        return self.bytes_written
    
    def truncate(self, size: int) -> None:
        if size < 0:
            raise ValueError("Truncation size cannot be negative")
    
    def flush(self, fsync: bool = False) -> None:
        if self.file:
            self.file.flush()
            if fsync or self.fsync:
                os.fsync(self.file.fileno())
    
    def tell(self) -> int:
        return self.file.tell()
    
    def finalize(self) -> Path:
        if not self.file:
            raise ProcessingError("Writer not initialized")
        
        self.flush(fsync=True)
        self.file.close()
        
        return self.filepath
    
    def close(self) -> None:
        if self.file:
            self.file.close()
            self.file = None