import os
import pandas as pd
from pathlib import Path
from typing import Tuple, Optional
from io import StringIO
import io

from etl.io.protocols import ResampleIOReader, ResampleIOWriter, ResampleIOIndexReaderWriter
from etl.exceptions import *

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
    
    def read_batch(self, batch_size: int) -> pd.DataFrame:
        header = "time,open,high,low,close,volume\n"
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
        print(f"exists:{Path(self.filepath).exists()} {self.filepath}")
        if not Path(self.filepath).exists():
            Path(self.filepath).parent.mkdir(parents=True, exist_ok=True)
            Path(self.filepath).touch()
            new_file = True
        
        self.file = open(self.filepath, 'r+', encoding=self.encoding, newline='')

        if new_file:
            self.bytes_written += self.file.write("time,open,high,low,close,volume\n")
        else:
            # first line always header
            self.file.readline()

    def write_batch(self, df: pd.DataFrame, offset: Optional[int] = None) -> int:
        df.index = df.index.strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        csv_str = df.to_csv(index=True, header=False)
        if offset:
            self.file.seek(offset)

        self.bytes_written += self.file.write(csv_str)
        return self.bytes_written
    
    def truncate(self, size: int) -> None:
        if size < 0:
            raise ValueError("Truncation size cannot be negative")

        self.file.truncate(size)
    
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


class ResampleIOIndexReaderWriterText(ResampleIOIndexReaderWriter):
    def __init__(self, index_path: Path, fsync: bool = False):
        self.index_path = index_path
        self.fsync = fsync
    
    def read(self) -> Tuple[int, int]:
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
        pass    