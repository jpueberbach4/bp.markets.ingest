import torch
import os
import pandas as pd
from typing import Any, List

from ml.space.space import Comet

class HaleBopp(Comet):
    """
    Standard Disk-Persistence Comet.
    Restored with elite gene debugging to identify solid matter dimensions.
    """
    
    def __init__(self, queue_size: int = 100):
        super().__init__(name="Hale-Bopp", queue_size=queue_size)
        os.makedirs("checkpoints", exist_ok=True)
        os.makedirs("logs", exist_ok=True)
        os.makedirs("debug", exist_ok=True)

    def dump_genes(self, generation: int, elite_indices: torch.Tensor, indicator_names: List[str]):
        """
        FIXED: Only writes the specific genes found by the elite model.
        """
        # Convert indices to list
        genes = elite_indices.cpu().numpy().tolist()
        
        # MAP only the active indices to names
        readable_genes = [indicator_names[i] for i in genes]
        
        timestamp = pd.Timestamp.now().strftime("%H%M%S")
        filename = f"debug/gen_{generation}_elite_active_{timestamp}.txt"
        
        with open(filename, "w") as f:
            f.write(f"--- Gen {generation} Elite Active Genes ---\n")
            # Write only the 24 active indicators
            for i, (idx, name) in enumerate(zip(genes, readable_genes)):
                f.write(f"Slot {i:02d} | Index {idx:02d} | {name}\n")
        
        # Keep the console clean
        print(f"🔬 [Hale-Bopp]: Materialized {len(readable_genes)} elite dimensions.")

    def eject(self, filename: str, data: Any, is_model: bool, is_gene_dump: bool = False):
        """Saves matter directly to the local file system."""
        
        # Route 1: Singularity Weights
        if is_model:
            torch.save(data, f"checkpoints/{filename}")
            
        # Route 2: Gene Debug Dump
        elif is_gene_dump:
            # Expects data to be a dict: {'gen': int, 'indices': tensor, 'names': list}
            self.dump_genes(data['gen'], data['indices'], data['names'])
            
        # Route 3: Universe History (Logs)
        else:
            with open(f"logs/{filename}", "a") as f:
                f.write(f"{data}\n")