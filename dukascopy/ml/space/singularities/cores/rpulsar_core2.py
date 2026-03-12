"""
===============================================================================
File:        rpulsar_core2.py
Author:      JP Ueberbach
Created:     2026-03-12
Revision:    Native PyTorch Rough Path Engine (Zero Dependency)

Description:
    Evolutionary neural feature-selection and signal-emission engine.

    This module implements a hybrid evolutionary optimization framework
    designed to discover high-value feature combinations and neural decision
    boundaries within large indicator spaces.

    *ROUGH PATH UPDATE*: This engine computes the Depth-2 Log-Signature
    using pure, native PyTorch tensor operations. It mathematically extracts
    the Lead-Lag Levy Area (cross-terms) without relying on external C++ 
    libraries like `signatory` or `roughpy`, ensuring maximum CUDA throughput
    and zero installation friction.

    Each individual in the population represents:
        • A sparse set of selected features ("genes")
        • A lightweight neural network operating on the Log-Signature
        • A signal threshold used for classification

    The system combines two optimization mechanisms:
        1. Gradient-based learning within individuals
        2. Genetic evolution across generations

Core Evolutionary Concepts:
    • Population-based search
    • Elitism (champion preservation)
    • Genetic crossover between individuals
    • Mutation of genes (with atomic W1 re-initialization)
    • Feature vitality tracking across generations

Neural Architecture (Signature-Aware):
    Each individual uses a lightweight feedforward network consisting of:

        Input:  Log-Signature(Path) + Absolute Basepoint
        Hidden: GELU activated dense layer
        Output: Single logit score

Signal Generation:
    Individuals emit binary signals using:
        sigmoid(logit) > threshold

Requirements:
    • Python 3.9+
    • PyTorch
    • NumPy
    • Pandas

===============================================================================
"""

import torch
import torch.nn.functional as F
import numpy as np
import pandas as pd

from ml.space.base import Fabric


class RPulsarCore2(Fabric):
    """
    Core evolutionary neural engine responsible for population management,
    neural computation, and genetic evolution via Native Rough Path Signatures.

    Attributes:
        config (dict): Runtime configuration dictionary.
        device (torch.device): CPU or CUDA device used for tensor operations.
        seed (int): Random seed used for deterministic behavior.

        pop_size (int): Number of individuals in the evolutionary population.
        gene_count (int): Number of features used per individual.
        hidden_dim (int): Size of the neural network hidden layer.

        sig_depth (int): Hardcoded to 2 for native PyTorch execution.
        sig_channels (int): The resulting dimensionality of the Log-Signature.
        input_dim (int): Total input dim (Log-Signature + Basepoint).

        population (torch.Tensor): Matrix storing feature indices per individual.
        thresholds (torch.Tensor): Classification threshold per individual.

        pop_W1 (torch.Tensor): First layer weight tensors per individual.
        pop_B1 (torch.Tensor): First layer bias tensors per individual.
        pop_W2 (torch.Tensor): Second layer weight tensors per individual.
        pop_B2 (torch.Tensor): Second layer bias tensors per individual.

        gene_scores (torch.Tensor): Running importance score for each feature.
        gene_usage (torch.Tensor): Count of how often each feature is used.

        lookback (int): Number of past timesteps used to construct the signature path.
    """

    def __init__(self, config, device, seed=42):
        self.config = config
        self.device = device
        self.seed = seed

        # Extract core hyperparameters
        self.pop_size = int(self.config.get('population_size', 1200))
        self.gene_count = int(self.config.get('gene_count', 16))
        self.hidden_dim = int(self.config.get('hidden_dim', 128))
        self.weight_mutation_rate = float(self.config.get("weight_mutation_rate", 0.005))
        self.verbose = bool(self.config.get("verbose", True))
        self.lookback = int(self.config.get('lookback', 8))

        # Rough Path Theory Configuration (Native Depth 2)
        self.sig_depth = 2 
        
        # Exact calculation for Depth 2 Free Lie Algebra dimensions:
        # Depth 1 = gene_count
        # Depth 2 = (gene_count * (gene_count - 1)) / 2  (Skew-symmetric upper triangle)
        self.sig_channels = self.gene_count + (self.gene_count * (self.gene_count - 1)) // 2
        
        # We append the Basepoint (current absolute value) to the signature 
        # to break translation invariance when needed.
        self.input_dim = self.sig_channels + self.gene_count

        if self.verbose:
            self.print(f"NATIVE_ROUGH_PATH_INIT: Channels={self.gene_count}, Depth={self.sig_depth}")
            self.print(f"NATIVE_ROUGH_PATH_INIT: LogSig Dim={self.sig_channels}, Total Input={self.input_dim}")

        # Deterministic generators
        self.torch_generator = torch.Generator(device='cpu').manual_seed(self.seed)
        if self.device.type == 'cuda':
            self.cuda_generator = torch.Generator(device=self.device).manual_seed(self.seed)
        else:
            self.cuda_generator = self.torch_generator

        # State tensors
        self.population = None
        self.thresholds = None
        self.pop_W1 = None
        self.pop_B1 = None
        self.pop_W2 = None
        self.pop_B2 = None

        self.gene_scores = None
        self.gene_usage = None
        self.feature_names = None
        
        # Cache triu indices for extremely fast Levy area extraction during forward pass
        self.triu_idx = torch.triu_indices(self.gene_count, self.gene_count, offset=1, device=self.device)

    def init_population(self, num_indicators: int, feature_names: list):
        self.feature_names = feature_names

        self.population = torch.stack([
            torch.tensor(
                np.random.choice(num_indicators, self.gene_count, replace=False),
                device=self.device
            )
            for _ in range(self.pop_size)
        ]).long()

        # W1 dimension is mapped to the Log-Signature + Basepoint
        self.pop_W1 = (
            torch.randn(self.pop_size, self.input_dim, self.hidden_dim, device=self.device)
            * np.sqrt(2.0 / self.input_dim)
        )

        self.pop_B1 = torch.zeros(self.pop_size, 1, self.hidden_dim, device=self.device)

        self.pop_W2 = (
            torch.randn(self.pop_size, self.hidden_dim, 1, device=self.device)
            * np.sqrt(2.0 / self.hidden_dim)
        )

        self.pop_B2 = torch.full((self.pop_size, 1, 1), -2.0, device=self.device)
        self.thresholds = torch.full((self.pop_size,), 0.40, device=self.device)

        self.gene_scores = torch.zeros(num_indicators, device=self.device)
        self.gene_usage = torch.zeros(num_indicators, device=self.device)

    def compute_native_logsig(self, path):
        """
        Computes the Depth-2 Log-Signature entirely within PyTorch.
        Path shape expected: (Batch, Time, Channels)
        """
        # 1. Depth 1: The simple path increment (Final - Initial)
        depth_1 = path[:, -1, :] - path[:, 0, :]
        
        # 2. Depth 2: The Levy Area (Iterated Cross-Integrals)
        # Using the discrete trapezoidal rule: 0.5 * sum(X_t * X_{t+1}^T - X_{t+1} * X_t^T)
        X_t = path[:, :-1, :]
        X_t_plus_1 = path[:, 1:, :]
        
        # Einstein summation for batched outer products over time
        # b = batch, t = time, i = channel 1, j = channel 2
        cross = torch.einsum('bti,btj->bij', X_t, X_t_plus_1) - torch.einsum('bti,btj->bij', X_t_plus_1, X_t)
        area = 0.5 * cross
        
        # The matrix is skew-symmetric, so we flatten only the upper triangle
        depth_2 = area[:, self.triu_idx[0], self.triu_idx[1]]
        
        return torch.cat([depth_1, depth_2], dim=1)

    def forward(self, x, w1, b1, w2, b2):
        """
        Execute the neural forward pass using Native Log-Signatures.
        """
        B, T, _ = x.shape

        # Unfold creates (Time, Gene, Lookback) -> Transpose to (Batch*Time, Lookback, Gene_Count)
        path = x.view(B * T, self.gene_count, self.lookback).transpose(1, 2)

        # Compute the Log-Signature natively
        logsig = self.compute_native_logsig(path)

        # Extract the Basepoint (the absolute state at the final step of the lookback)
        basepoint = path[:, -1, :]

        # Concatenate geometric features with absolute features
        features = torch.cat([logsig, basepoint], dim=1)
        
        # Reshape back to sequence batch format for the neural layers
        features = features.view(B, T, self.input_dim)

        # Feedforward
        h1 = torch.bmm(features, w1)
        h1 = F.gelu(h1 + b1)

        return torch.bmm(h1, w2) + b2

    def evolve(self, latest_f1, latest_score):
        f1_scores = latest_f1.to(self.device).flatten()
        primary_scores = latest_score.to(self.device).flatten()

        gen_best_f1_val, gen_best_f1_idx = torch.max(f1_scores, dim=0)

        champ_pop = self.population[gen_best_f1_idx].clone()
        champ_w1 = self.pop_W1[gen_best_f1_idx].clone()
        champ_b1 = self.pop_B1[gen_best_f1_idx].clone()
        champ_w2 = self.pop_W2[gen_best_f1_idx].clone()
        champ_b2 = self.pop_B2[gen_best_f1_idx].clone()
        champ_thresh = self.thresholds[gen_best_f1_idx].clone()

        idx = torch.argsort(primary_scores, descending=True)

        self.population = self.population[idx]
        self.thresholds = self.thresholds[idx]
        self.pop_W1, self.pop_B1 = self.pop_W1[idx], self.pop_B1[idx]
        self.pop_W2, self.pop_B2 = self.pop_W2[idx], self.pop_B2[idx]

        keep = max(2, self.pop_size // 10)

        new_pop = self.population.clone()
        new_w1, new_b1 = self.pop_W1.clone(), self.pop_B1.clone()
        new_w2, new_b2 = self.pop_W2.clone(), self.pop_B2.clone()
        new_thresh = self.thresholds.clone()

        new_pop[1] = champ_pop
        new_w1[1], new_b1[1] = champ_w1, champ_b1
        new_w2[1], new_b2[1] = champ_w2, champ_b2
        new_thresh[1] = champ_thresh

        if self.verbose:
            self.print("CORE_QUANTUM_LOCK", f1=gen_best_f1_val.item())

        mutation_std = self.weight_mutation_rate

        for i in range(keep, self.pop_size):
            p1, p2 = torch.randint(0, keep, (2,), generator=self.torch_generator)

            if torch.rand(1, generator=self.torch_generator).item() < 0.7:
                # CROSSOVER
                cut = torch.randint(0, self.gene_count, (1,), generator=self.torch_generator).item()
                child_genes = torch.cat([self.population[p1, :cut], self.population[p2, cut:]])
                
                alpha = torch.rand(1, device=self.device, generator=self.cuda_generator) * 0.2 + 0.4
                child_b1 = alpha * self.pop_B1[p1] + (1 - alpha) * self.pop_B1[p2]

                unique_genes = torch.unique(child_genes)

                if len(unique_genes) < self.gene_count:
                    used_mask = torch.zeros(len(self.feature_names), dtype=torch.bool, device=self.device)
                    used_mask[unique_genes] = True
                    available = torch.where(~used_mask)[0]
                    needed = self.gene_count - len(unique_genes)
                    perm = torch.randperm(len(available), generator=self.torch_generator)[:needed]
                    final_genes = torch.cat([unique_genes, available[perm]])
                else:
                    final_genes = child_genes

                # Because cross-terms define the entire geometry of the path, we cannot splice W1.
                # W1 is initialized fresh to learn the new geometric Lie algebra mapping.
                final_w1 = torch.randn(
                    (self.input_dim, self.hidden_dim),
                    device=self.device
                ) * np.sqrt(2.0 / self.input_dim)

                new_pop[i] = final_genes
                new_w1[i] = final_w1
                new_b1[i] = child_b1
                new_w2[i] = alpha * self.pop_W2[p1] + (1 - alpha) * self.pop_W2[p2]
                new_b2[i] = alpha * self.pop_B2[p1] + (1 - alpha) * self.pop_B2[p2]
                new_thresh[i] = alpha * self.thresholds[p1] + (1 - alpha) * self.thresholds[p2]

            else:
                # MUTATION
                child_genes = self.population[p1].clone()
                child_w1 = self.pop_W1[p1].clone()
                child_b1 = self.pop_B1[p1].clone()

                if torch.rand(1, generator=self.torch_generator).item() < 0.3:
                    n_mutations = torch.randint(
                        1, min(4, self.gene_count), (1,),
                        generator=self.torch_generator
                    ).item()

                    for _ in range(n_mutations):
                        used_mask = torch.zeros(len(self.feature_names), dtype=torch.bool, device=self.device)
                        used_mask[child_genes] = True
                        available = torch.where(~used_mask)[0]

                        if len(available) > 0:
                            pos = torch.randint(0, self.gene_count, (1,), generator=self.torch_generator).item()
                            new_gene = available[
                                torch.randint(0, len(available), (1,), generator=self.torch_generator)
                            ].item()
                            child_genes[pos] = new_gene

                    # A mutated gene pool means mutated cross-terms. W1 must reset.
                    child_w1 = torch.randn(
                        (self.input_dim, self.hidden_dim),
                        device=self.device
                    ) * np.sqrt(2.0 / self.input_dim)

                new_pop[i] = child_genes
                new_w1[i] = child_w1 + torch.randn_like(child_w1) * mutation_std
                new_b1[i] = child_b1 + torch.randn_like(child_b1) * mutation_std * 0.1
                new_w2[i] = self.pop_W2[p1] + torch.randn_like(self.pop_W2[p1]) * mutation_std
                new_b2[i] = self.pop_B2[p1] + torch.randn_like(self.pop_B2[p1]) * mutation_std * 0.1
                new_thresh[i] = self.thresholds[p1] + torch.randn(
                    1, device=self.device, generator=self.cuda_generator
                ).squeeze() * 0.01

        self.population = new_pop
        self.pop_W1, self.pop_B1 = new_w1, new_b1
        self.pop_W2, self.pop_B2 = new_w2, new_b2
        self.thresholds = torch.clamp(new_thresh, 0.10, 0.85)

    def run_atomic_scan(self):
        vitality = (self.gene_scores + 0.1) / (self.gene_usage + 1.0)
        pool_size = max(int(self.gene_count * 1.5), 40)
        pool_size = min(pool_size, len(self.feature_names))
        pool = torch.argsort(vitality, descending=True)[:pool_size]

        assert len(pool) == len(torch.unique(pool)), "Vitality pool contains duplicates!"

        start_idx = int(self.pop_size * 0.8)

        for i in range(start_idx, self.pop_size):
            self.population[i] = pool[
                torch.randperm(len(pool), generator=self.torch_generator)[:self.gene_count]
            ].to(self.device)

            self.pop_W1[i] = (
                torch.randn(
                    self.input_dim,
                    self.hidden_dim,
                    device=self.device,
                    generator=self.cuda_generator
                ) * np.sqrt(2.0 / self.input_dim)
            )

            self.pop_W2[i] = (
                torch.randn(
                    self.hidden_dim,
                    1,
                    device=self.device,
                    generator=self.cuda_generator
                ) * np.sqrt(2.0 / self.hidden_dim)
            )
            self.pop_B2[i] = -2.0

    def emit(self, features: pd.DataFrame) -> np.ndarray:
        if len(features) < self.lookback:
            return np.array([False] * len(features))

        with torch.no_grad():
            x = torch.tensor(features.values.astype(np.float32), device=self.device)
            x_sel = x[:, self.population[0]]
            
            windows = x_sel.unfold(dimension=0, size=self.lookback, step=1)
            windows = windows.unsqueeze(0).reshape(1, windows.size(0), -1)

            logits = self.forward(
                windows,
                self.pop_W1[0:1],
                self.pop_B1[0:1],
                self.pop_W2[0:1],
                self.pop_B2[0:1],
            )

            preds = (torch.sigmoid(logits) > self.thresholds[0]).cpu().numpy().flatten()
            padding = np.array([False] * (self.lookback - 1))

            return np.concatenate([padding, preds])