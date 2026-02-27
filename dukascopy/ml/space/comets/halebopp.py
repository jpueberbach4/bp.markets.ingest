"""
===============================================================================
File:        halebopp.py
Author:      JP Ueberbach
Created:     2026-02-23

Description:
    Implementation of the Hale-Bopp comet within the ML space.

    Hale-Bopp is a standard disk-persistence comet designed for elite gene
    debugging and feature extraction. It supports:
        - Dumping elite genes to human-readable format
        - Saving model weights or data payloads
        - Logging universe history

Key Capabilities:
    - Elite gene persistence and debugging
    - Configurable queue size
    - Safe local storage of model and log data
===============================================================================
"""

import os
from typing import Any, List

import torch
import pandas as pd

from ml.space.space import Comet


class HaleBopp(Comet):
    """Standard disk-persistence comet with elite gene tracking."""

    def __init__(self, queue_size: int = 100):
        """Initialize Hale-Bopp comet and ensure storage directories exist.

        Args:
            queue_size (int, optional): Maximum size of internal processing queue.
                Defaults to 100.
        """
        super().__init__(name="Hale-Bopp", queue_size=queue_size)
        os.makedirs("checkpoints", exist_ok=True)
        os.makedirs("logs", exist_ok=True)
        os.makedirs("debug", exist_ok=True)

    def dump_genes(self, generation: int, elite_indices: torch.Tensor, indicator_names: List[str]):
        """Dump elite genes from a generation into a human-readable debug file.

        Only the active indices identified by the elite model are written.

        Args:
            generation (int): The current generation number.
            elite_indices (torch.Tensor): Tensor of elite gene indices.
            indicator_names (List[str]): List of all indicator names.
        """
        # Convert tensor indices to list
        genes = elite_indices.cpu().numpy().tolist()

        # Map active indices to readable names
        readable_genes = [indicator_names[i] for i in genes]

        timestamp = pd.Timestamp.now().strftime("%H%M%S")
        filename = f"debug/gen_{generation}_elite_active_{timestamp}.txt"

        # Write active genes to file
        with open(filename, "w") as f:
            f.write(f"--- Gen {generation} Elite Active Genes ---\n")
            for i, (idx, name) in enumerate(zip(genes, readable_genes)):
                f.write(f"Slot {i:02d} | Index {idx:02d} | {name}\n")

        # Console feedback
        self.print("HALEBOPP_DUMPGENES", count=len(readable_genes))

    def eject(self, filename: str, data: Any, is_model: bool, is_gene_dump: bool = False):
        """Save data to the local file system based on type.

        Routes:
            - Model weights to 'checkpoints/'
            - Elite gene dump to 'debug/'
            - Universe history/logs to 'logs/'

        Args:
            filename (str): Name of the output file.
            data (Any): Data to save (model, gene dump info, or log entry).
            is_model (bool): If True, treat data as model weights.
            is_gene_dump (bool, optional): If True, treat data as elite gene dump.
                Defaults to False.
        """
        if is_model:
            # Save PyTorch model weights
            self.print("HALEBOPP_EJECT", filename=filename)
            torch.save(data, f"checkpoints/{filename}")

        elif is_gene_dump:
            # Expects data as dict: {'gen': int, 'indices': tensor, 'names': list}
            self.dump_genes(data['gen'], data['indices'], data['names'])

        else:
            # Append universe history/log entry
            with open(f"logs/{filename}", "a") as f:
                f.write(f"{data}\n")