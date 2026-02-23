from abc import ABC, abstractmethod
from typing import Any
import os
import queue
import threading
import torch
import torch.nn as nn
import pandas as pd
import numpy as np

# Mocking the data provider - ensure this is available in your environment
# from your_data_module import get_data 

class Universe(ABC):
    """Baseclass for feature universes."""
    @abstractmethod
    def ignite(self, after_ms, limit): pass

    @abstractmethod
    def dimensions(self): pass

    @abstractmethod
    def features(self): pass

    @abstractmethod
    def bigbang(self): pass

class Normalizer(nn.Module, ABC):
    """
    Abstract Base Class for feature scaling.
    Defines the laws of atmospheric entry for raw data.
    """
    def __init__(self):
        super().__init__()

    @abstractmethod
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        pass

class Comet(ABC):
    """
    Abstract Base Class for the Async Data Comet.
    Defines the orbital mechanics for non-blocking data ejection.
    """

    def __init__(self, name: str, queue_size: int = 100):
        self.name = name
        self._trail = queue.Queue(maxsize=queue_size)
        self._nucleus = threading.Thread(target=self._orbital_loop, daemon=True)
        
        # Standardize the planetary storage environment
        os.makedirs('checkpoints', exist_ok=True)
        os.makedirs('logs', exist_ok=True)
        
        self._nucleus.start()
        print(f"☄️ [Space]: Establishing Orbit for {self.name}. Tail length: {queue_size}")

    def _orbital_loop(self):
        """Standardizes the loop that consumes the trail."""
        while True:
            item = self._trail.get()
            if item is None: 
                break
                
            filename, data, is_model = item
            try:
                self.eject(filename, data, is_model)
            except Exception as e:
                print(f"❌ [Comet {self.name} Error]: Critical failure in ejection: {e}")
            finally:
                self._trail.task_done()

    @abstractmethod
    def eject(self, filename: str, data: Any, is_model: bool):
        """
        The concrete implementation of how matter is written to the void.
        Must be implemented by specific comet types.
        """
        pass

    def deposit(self, filename: str, data: Any, is_model: bool = False, is_gene_dump: bool = False):
        """
        Public method to add matter to the trail without blocking the main thread.
        """
        try:
            self._trail.put((filename, data, is_model), block=False)
        except queue.Full:
            if not is_model:
                # Discard logs to preserve velocity
                pass 
            else:
                # Block for models; we cannot lose the mass of a new discovery
                self._trail.put((filename, data, is_model), block=True)

    def dissipate(self):
        """Gracefully ends the comet's flight path."""
        self._trail.put(None)
        self._nucleus.join()
        print(f"☄️ [Comet {self.name}]: Dissipated into the cosmos.")


class Singularity(ABC):
    """
    The computational core where the multi-dimensional feature space
    collapses into a predictive output.
    """

    def __init__(self, device: str = "cuda" if torch.cuda.is_available() else "cpu"):
        self.device = torch.device(device)
        self.model = None
        print(f"🌀 [Singularity]: Initialized on {self.device}")

    @abstractmethod
    def compress(self, features: pd.DataFrame, targets: pd.Series):
        """
        The entry point for the Big Bang matter. 
        Should handle tensor conversion and the start of the 'collapse' (training).
        """
        pass

    @abstractmethod
    def emit(self, features: pd.DataFrame) -> np.ndarray:
        """
        The inference path. Takes a coordinate space and 
        emits a prediction signal.
        """
        pass

    def to_tensor(self, df: pd.DataFrame) -> torch.Tensor:
        """
        Standardizes the transition of matter from CPU/Pandas 
        to GPU/Torch.
        """
        return torch.tensor(df.values, dtype=torch.float32).to(self.device)

    @abstractmethod
    def save_state(self, path: str):
        """Preserves the singularity's current mass (weights)."""
        pass

class Lens(nn.Module, ABC):
    """
    Abstract Base Class for all loss functions.
    A Lens defines how the Singularity perceives its own errors.
    """
    def __init__(self):
        super().__init__()

    @abstractmethod
    def forward(self, inputs: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        """
        Calculates the divergence between the Singularity's 
        output and the ground truth.
        """
        pass

