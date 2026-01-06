import os
import io
from pathlib import Path
from typing import Tuple, Optional, BinaryIO, TextIO

class BaseIO:
    def __init__(self, input_path: Path, output_path: Path, index_path: Path, fsync: bool = False):
        self.input_path = input_path
        self.output_path = output_path
        self.index_path = index_path
        self.fsync = fsync
        self._f_in: Optional[BinaryIO] = None
        self._f_out: Optional[TextIO] = None

    def open(self, mode_in: str = "rb", mode_out: str = "r+"):
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.output_path.exists():
            self.output_path.touch()
            
        self._f_in = open(self.input_path, mode_in)
        self._f_out = open(self.output_path, mode_out)

    def read_index(self) -> Tuple[int, int]:
        if not self.index_path or not self.index_path.exists():
            return 0, 0
        with open(self.index_path, "r") as f:
            lines = f.readlines()
            return int(lines[0].strip()), int(lines[1].strip())

    def write_index(self, input_pos: int, output_pos: int):
        temp_path = self.index_path.with_suffix(".tmp")
        with open(temp_path, "w") as f:
            f.write(f"{input_pos}\n{output_pos}")
            f.flush()
            if self.fsync: os.fsync(f.fileno())
        os.replace(temp_path, self.index_path)

    def close(self):
        if self._f_in: self._f_in.close()
        if self._f_out: self._f_out.close()