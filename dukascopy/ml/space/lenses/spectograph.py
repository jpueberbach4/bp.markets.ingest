"""
===============================================================================
File:        spectrograph.py
Author:      JP Ueberbach
Created:     2026-02-23

Description:
    Implementation of a Spectrograph instrument within the ML space.

    The Spectrograph manages the selection and application of different Lens
    modules to compute losses or metrics during training, allowing flexible
    analysis of model performance. Supports focal loss for rare-event
    magnification and standard BCE loss for baseline evaluation.

Key Capabilities:
    - Factory-based lens instantiation
    - Focal loss computation for rare positive events
    - Standard binary cross-entropy loss support
    - Integration with PyTorch training pipelines
===============================================================================
"""

from ml.space.space import Lens
from ml.space.lenses.gravitational import GravitationalLens
from ml.space.lenses.standardeye import StandardEye
import torch


class Spectrograph:
    """Instrument for managing and applying different Lenses to model outputs."""

    def __init__(self, mode: str, **kwargs):
        """
        Initializes the Spectrograph with a specified lens mode.

        Args:
            mode (str): The lens type to use. Supported modes: 'focal', 'bce'.
            **kwargs: Additional keyword arguments passed to the lens constructor.
        """
        self.mode = mode
        self.lens = self._ignite_lens(mode, **kwargs)
        print(f"🔬 [Spectrograph]: Instrument active using {self.lens.__class__.__name__} configuration.")

    def _ignite_lens(self, mode: str, **kwargs) -> Lens:
        """
        Factory method to instantiate the requested Lens.

        Args:
            mode (str): Lens type identifier.
            **kwargs: Arguments forwarded to the lens constructor.

        Returns:
            Lens: Instantiated lens object.

        Raises:
            ValueError: If an unknown lens mode is provided.
        """
        if mode == "focal":
            return GravitationalLens(**kwargs)
        elif mode == "bce":
            return StandardEye(**kwargs)
        else:
            raise ValueError(f"❌ [Spectrograph Error]: Unknown lens mode: {mode}")

    def analyze(self, inputs: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        """
        Applies the lens to inputs and targets to compute loss.

        Args:
            inputs (torch.Tensor): Model predictions (logits or probabilities).
            targets (torch.Tensor): Ground-truth labels.

        Returns:
            torch.Tensor: Loss values computed by the lens.
        """
        return self.lens(inputs, targets)