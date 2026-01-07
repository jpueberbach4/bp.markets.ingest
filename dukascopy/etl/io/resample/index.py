import os
from pathlib import Path
from typing import Tuple

from etl.exceptions import IndexCorruptionError, IndexValidationError, IndexWriteError

class ResampleIOIndexReaderWriter:
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