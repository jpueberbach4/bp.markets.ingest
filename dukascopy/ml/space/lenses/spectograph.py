
from ml.space.space import Lens
from ml.space.lenses.gravitational import GravitationalLens
from ml.space.lenses.standardeye import StandardEye
import torch
import torch.nn as nn

class Spectrograph:
    """
    The Base Instrument.
    Manages the selection and application of different Lenses
    to analyze the model's performance.
    """
    def __init__(self, mode: str, **kwargs):
        self.mode = mode
        self.lens = self._ignite_lens(mode, **kwargs)
        print(f"🔬 [Spectrograph]: Instrument active using {self.lens.__class__.__name__} configuration.")

    def _ignite_lens(self, mode: str, **kwargs) -> Lens:
        """
        Factory method to manifest the requested lens.
        """
        if mode == "focal":
            return GravitationalLens(**kwargs)
        elif mode == "bce":
            return StandardEye(**kwargs)
        else:
            raise ValueError(f"❌ [Spectrograph Error]: Unknown lens mode: {mode}")

    def analyze(self, inputs: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        """
        Passes the data through the lens to calculate loss.
        """
        return self.lens(inputs, targets)
    