from ml.space.space import Normalizer
import torch
from typing import List

class Kinematics(Normalizer):
    """
    A 4-Dimensional Kinematic Normalizer.
    Expands indicators into:
    1. Direction (_dir): Sign of the value.
    2. Velocity (_vel): 1st Derivative (Change).
    3. Acceleration (_acc): 2nd Derivative (Rate of Change).
    4. Magnitude (_mag): Absolute relative mass (Abs value).
    """
    def __init__(self, dim=0, fill_value=0.0):
        super().__init__()
        self.dim = dim
        self.fill_value = fill_value
        self.suffixes = ["_dir", "_vel", "_acc", "_mag"]

    def generate_names(self, input_names: List[str]) -> List[str]:
        # Guard against double-concatenation (dir_dir)
        if any(input_names[0].endswith(s) for s in self.suffixes):
            return input_names

        output_names = []
        for suffix in self.suffixes:
            for name in input_names:
                output_names.append(f"{name}{suffix}")
        return output_names

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # 1. Direction (Sign)
        direction = torch.sign(x)

        # 2. Velocity (1st Derivative)
        shifted_x = torch.roll(x, shifts=1, dims=self.dim)
        velocity = x - shifted_x
        
        # 3. Acceleration (2nd Derivative)
        shifted_v = torch.roll(velocity, shifts=1, dims=self.dim)
        acceleration = velocity - shifted_v

        # 4. Magnitude
        # Captures the absolute intensity of the normalized signal
        magnitude = torch.abs(x)
        
        # Clean the "roll" noise on the CUDA path
        if x.size(self.dim) > 0:
            v_idx = torch.tensor([0], device=x.device)
            velocity.index_fill_(self.dim, v_idx, self.fill_value)
            
            a_idx = torch.tensor([0, 1], device=x.device)
            acceleration.index_fill_(self.dim, a_idx, self.fill_value)

        return torch.cat([direction, velocity, acceleration, magnitude], dim=-1)