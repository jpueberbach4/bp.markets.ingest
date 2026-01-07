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
     
