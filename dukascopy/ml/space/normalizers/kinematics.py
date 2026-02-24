"""
===============================================================================
File:        kinematics.py
Author:      JP Ueberbach
Created:     2026-02-23

Description:
    Implementation of a Kinematics normalizer within the ML space.

    Kinematics selectively expands eligible features into four physical
    dimensions: direction, velocity, acceleration, and magnitude. Non-matching
    features pass through unchanged as static features. Supports 2D and 3D
    tensor inputs for batch or sequence processing.

Key Capabilities:
    - 4-dimensional expansion of filtered features
    - Maintains static features for non-selected inputs
    - Handles 2D [Rows, Features] and 3D [Batch, Seq, Features] tensors
    - Device-aware mask registration for GPU/CPU safety
===============================================================================
"""

import torch
import fnmatch
from typing import List
from ml.space.space import Normalizer


class Kinematics(Normalizer):
    """
    Selective 4D Kinematic Normalizer.
    
    Expands filtered features into direction, velocity, acceleration, and
    magnitude, while passing through static features unchanged.
    """
    def __init__(self, config: dict):
        """
        Args:
            config (dict): Configuration dictionary with optional keys:
                - dim (int): sequence dimension for 3D tensors (default 1)
                - fill_value (float): value to initialize edge derivatives (default 0.0)
                - filter (dict): dictionary with 'inclusive' list of feature patterns
        """
        super().__init__()
        self.dim = config.get('dim', 1)
        self.fill_value = config.get('fill_value', 0.0)
        self.config = config
        self.suffixes = [":dir", ":vel", ":acc", ":mag"]
        self.inclusive_filters = config.get('filter', {}).get('inclusive', [])
        
        # Buffer for eligible mask (mapped to device automatically)
        self.register_buffer("eligible_mask", torch.empty(0, dtype=torch.bool), persistent=False)
        self.eligible_indices: List[int] = []

    def _is_eligible(self, name: str) -> bool:
        """Check if a feature name matches any inclusive pattern."""
        return any(fnmatch.fnmatch(name.lower(), pattern.lower()) for pattern in self.inclusive_filters)

    def generate_names(self, input_names: List[str]) -> List[str]:
        """
        Generate expanded feature names based on eligibility.
        
        Args:
            input_names (List[str]): List of original feature names.
        
        Returns:
            List[str]: List of feature names after expansion.
        """
        self.eligible_indices = [i for i, name in enumerate(input_names) if self._is_eligible(name)]
        
        output_names = []
        # Add static features first
        for i, name in enumerate(input_names):
            if i not in self.eligible_indices:
                output_names.append(name)
        # Add expanded kinematic features
        for suffix in self.suffixes:
            for i in self.eligible_indices:
                output_names.append(f"{input_names[i]}{suffix}")
        return output_names

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Expand eligible features into 4D kinematic representation.
        
        Handles:
        - 2D tensors: [Rows, Features]
        - 3D tensors: [Batch, Seq, Features]
        
        Args:
            x (torch.Tensor): Input tensor of shape [*, Features]
        
        Returns:
            torch.Tensor: Expanded tensor with kinematic features concatenated
                          to static features.
        """
        print(f"🌌 [Space]: Establishing physics. Kinematics.")

        if not self.eligible_indices:
            return x

        # Initialize mask if needed
        if self.eligible_mask.size(0) != x.size(-1):
            mask = torch.zeros(x.size(-1), dtype=torch.bool, device=x.device)
            mask[self.eligible_indices] = True
            self.eligible_mask = mask

        # Split static vs eligible features
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
        velocity = kinematic_source - torch.roll(kinematic_source, shifts=1, dims=calc_dim)
        acceleration = velocity - torch.roll(velocity, shifts=1, dims=calc_dim)
        magnitude = torch.abs(kinematic_source)

        # Clear artifacts from roll operations
        if kinematic_source.size(calc_dim) > 1:
            velocity.narrow(calc_dim, 0, 1).fill_(self.fill_value)
            acceleration.narrow(calc_dim, 0, min(2, acceleration.size(calc_dim))).fill_(self.fill_value)

        # Concatenate features in order: static, dir, vel, acc, mag
        return torch.cat([static_features, direction, velocity, acceleration, magnitude], dim=-1)