"""
===============================================================================
File:        network.py
Author:      JP Ueberbach
Created:     2026-03-01

Description:
    Neural network inference module for MilkyWay model execution.

    This module defines the concrete neural architecture used for inference
    in neuro-evolved MilkyWay models. It implements a simple feedforward
    network with a single hidden layer and a scalar output, intended for
    binary decision or probability estimation tasks.

    The network is designed to be lightweight, serializable, and compatible
    with evolutionary weight mutation and post-hoc inspection tooling.

Responsibilities:
    - Define a deterministic forward inference path
    - Expose intermediate activations for diagnostic analysis
    - Serve as the canonical runtime representation of evolved models

Design Notes:
    - Uses GELU activation for hidden-layer nonlinearity
    - Uses Sigmoid activation for bounded scalar output
    - Returns intermediate tensors to support forensic inspection
    - Assumes a single-output architecture
===============================================================================
"""
import torch.nn as nn


class SingularityInference(nn.Module):
    """
    Standard predictive core for MilkyWay neuro-evolved models.

    This module implements a minimal fully connected neural network
    consisting of one hidden layer and one output layer, with explicit
    exposure of intermediate computation stages.
    """

    def __init__(self, input_dim: int, hidden_dim: int):
        """
        Initializes the neural network layers.

        Args:
            input_dim (int): Number of input features expected by the model.
            hidden_dim (int): Number of neurons in the hidden layer.
        """
        # Initialize the base PyTorch Module so parameters are registered correctly
        super(SingularityInference, self).__init__()

        # Define the first linear transformation from input space to hidden space
        self.l1 = nn.Linear(input_dim, hidden_dim)

        # Define the second linear transformation from hidden space to scalar output
        self.l2 = nn.Linear(hidden_dim, 1)

        # Define the non-linear activation applied after the first linear layer
        self.activation = nn.GELU()

        # Define the output activation to squash values into the (0, 1) range
        self.out_act = nn.Sigmoid()

    def forward(self, x):
        """
        Performs a forward inference pass through the network.

        Args:
            x (torch.Tensor): Input tensor of shape (batch_size, input_dim).

        Returns:
            Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
                - Output after sigmoid activation
                - Pre-activation hidden layer output
                - Post-activation hidden layer output
                - Pre-activation output layer value
        """
        # Apply the first linear transformation to the input tensor
        h1 = self.l1(x)

        # Apply the non-linear activation to the hidden representation
        a1 = self.activation(h1)

        # Apply the second linear transformation to produce a scalar logit
        s2 = self.l2(a1)

        # Apply sigmoid activation and return output along with intermediates
        return self.out_act(s2), h1, a1, s2