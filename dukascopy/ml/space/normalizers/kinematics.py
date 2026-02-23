import torch
import fnmatch
from typing import List

# Assuming Normalizer is imported from your base module
from ml.space.space import Normalizer

class Kinematics(Normalizer):
    """
    A Selective 4-Dimensional Kinematic Normalizer.
    Expands only filtered indicators into: dir, vel, acc, mag.
    Non-matching indicators pass through as 'static' features.
    """
    def __init__(self, config):
        super().__init__()
        self.dim = config.get('dim', 1)  # Sequence/time dimension for 3D tensors
        self.fill_value = config.get('fill_value', 0.0)
        self.config = config
        self.suffixes = [":dir", ":vel", ":acc", ":mag"]
        
        # Extract filters from config
        self.inclusive_filters = config.get('filter', {}).get('inclusive', [])
        
        # Correctly register the buffer as an empty boolean tensor
        self.register_buffer("eligible_mask", torch.empty(0, dtype=torch.bool), persistent=False)
        self.eligible_indices = []

    def _is_eligible(self, name: str) -> bool:
        """Check if a feature name matches any inclusive pattern."""
        return any(fnmatch.fnmatch(name.lower(), pattern.lower()) for pattern in self.inclusive_filters)

    def generate_names(self, input_names: List[str]) -> List[str]:
        # Identify indices that match our kinematic criteria
        self.eligible_indices = [i for i, name in enumerate(input_names) if self._is_eligible(name)]
        
        output_names = []
        # 1. Non-eligible features (Static)
        for i, name in enumerate(input_names):
            if i not in self.eligible_indices:
                output_names.append(name)
        
        # 2. Expanded features (Physics Laws)
        for suffix in self.suffixes:
            for i in self.eligible_indices:
                output_names.append(f"{input_names[i]}{suffix}")
                
        return output_names

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Handles both:
        2D: [Rows, Features] -> for bigbang() initialization
        3D: [Batch, Seq, Features] -> for live inference
        """
        if not self.eligible_indices:
            return x

        # Safely initialize the mask on the correct device if size doesn't match
        if self.eligible_mask.size(0) != x.size(-1):
            mask = torch.zeros(x.size(-1), dtype=torch.bool, device=x.device)
            mask[self.eligible_indices] = True
            # Updating the registered buffer correctly maps it to the device
            self.eligible_mask = mask

        # Dimension-safe slicing (Fixes the IndexError)
        if x.dim() == 3:
            static_features = x[:, :, ~self.eligible_mask]
            kinematic_source = x[:, :, self.eligible_mask]
            calc_dim = self.dim
        elif x.dim() == 2:
            static_features = x[:, ~self.eligible_mask]
            kinematic_source = x[:, self.eligible_mask]
            calc_dim = 0
        else:
            raise ValueError(f"Kinematics expected 2D or 3D tensor, got {x.dim()}D")

        # --- Compute Physics ---
        direction = torch.sign(kinematic_source)

        # Velocity (1st Derivative)
        shifted_x = torch.roll(kinematic_source, shifts=1, dims=calc_dim)
        velocity = kinematic_source - shifted_x
        
        # Acceleration (2nd Derivative)
        shifted_v = torch.roll(velocity, shifts=1, dims=calc_dim)
        acceleration = velocity - shifted_v

        # Magnitude
        magnitude = torch.abs(kinematic_source)
        
        # --- Clean CUDA Roll Artifacts ---
        if kinematic_source.size(calc_dim) > 1:
            # Velocity: clear first index
            velocity.narrow(calc_dim, 0, 1).fill_(self.fill_value)
            # Acceleration: clear first two indices
            acceleration.narrow(calc_dim, 0, min(2, acceleration.size(calc_dim))).fill_(self.fill_value)

        # Concatenate in order: [Static, Dirs, Vels, Accs, Mags]
        return torch.cat([
            static_features, 
            direction, 
            velocity, 
            acceleration, 
            magnitude
        ], dim=-1)