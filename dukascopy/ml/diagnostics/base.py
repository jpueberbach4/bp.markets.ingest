"""
===============================================================================
File:        base.py
Author:      JP Ueberbach
Created:     2026-03-01

Description:
    Foundational infrastructure module for the MilkyWay ML framework.

    This module defines the lowest-level abstract building blocks used
    throughout the system. It establishes strict contracts for diagnostic
    tooling that operates on persisted PyTorch model checkpoints.

    The intent of this module is to provide:
        - A common interface for diagnostic execution
        - Centralized device resolution (CPU vs CUDA)
        - Safe and validated model checkpoint loading
        - Enforced subclass behavior via abstract base classes

    This file is deliberately minimal and contains no business logic.
    It exists solely to define structure, expectations, and guarantees
    for downstream diagnostic implementations.

Design Notes:
    - All subclasses MUST implement the `run()` method.
    - Model checkpoints are loaded eagerly during initialization.
    - CUDA is used automatically when available.
    - Initialization fails fast if the model path is invalid.
===============================================================================
"""
import os
from abc import ABC, abstractmethod
import torch


class BaseDiagnostic(ABC):
    """
    Abstract base class for all MilkyWay diagnostic tools.

    This class defines the required initialization workflow and enforces
    the existence of a diagnostic execution entry point via `run()`.
    """

    def __init__(self, model_path: str):
        """
        Initializes the diagnostic with a model checkpoint.

        Args:
            model_path (str): Filesystem path to a serialized PyTorch
                model checkpoint to be inspected or analyzed.

        Raises:
            FileNotFoundError: If the provided model path does not exist.
        """
        # Store the full path to the model checkpoint
        self.model_path = model_path

        # Extract just the filename from the full path (no directories)
        self.model_name = os.path.basename(model_path)

        # Select CUDA if available, otherwise fall back to CPU
        self.device = torch.device(
            'cuda' if torch.cuda.is_available() else 'cpu'
        )

        # Verify that the model checkpoint file actually exists on disk
        if not os.path.exists(self.model_path):
            # Fail immediately if the file cannot be found
            raise FileNotFoundError(
                f"🚨 [Error]: Model checkpoint not found at {self.model_path}"
            )

        # Load the checkpoint into memory, mapping tensors to the chosen device
        self.checkpoint = torch.load(
            self.model_path,
            map_location=self.device,
            weights_only=False
        )

    @abstractmethod
    def run(self):
        """
        Executes the primary diagnostic routine.

        Subclasses must implement this method to perform their specific
        analysis, reporting, or validation logic.

        Returns:
            None
        """
        # This method must be overridden by subclasses
        pass