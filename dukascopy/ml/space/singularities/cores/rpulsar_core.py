"""
===============================================================================
File:        rpulsar_core.py
Author:      JP Ueberbach
Created:     2026-03-08
Revision:    1D-CNN Sequence Architecture Update

Description:
    Evolutionary neural feature-selection and signal-emission engine.

    This module implements a hybrid evolutionary optimization framework
    designed to discover high-value feature combinations and neural decision
    boundaries within large indicator spaces.

    Each individual in the population represents:

        • A sparse set of selected features ("genes")
        • A 1D Convolutional Neural Network (CNN) operating on those features
        • A signal threshold used for classification

    The system combines two optimization mechanisms:

        1. Gradient-based learning within individuals
        2. Genetic evolution across generations

Core Evolutionary Concepts:
    • Population-based search
    • Elitism (champion preservation)
    • Genetic crossover between individuals (Gene-level Conv filter swapping)
    • Mutation of both genes and neural weights
    • Feature vitality tracking across generations

Neural Architecture (1D-CNN):
    Each individual uses a Convolutional network to preserve chronological sequence:

        Input:  (Gene_Count, Lookback window)
        Conv1D: Sweeps a chronological kernel across time
        Pool1D: Extracts dominant structural peaks
        Hidden: GELU activation
        Output: Single logit score

Signal Generation:
    Individuals emit binary signals using:

        sigmoid(logit) > threshold

    Thresholds evolve alongside the network weights.

===============================================================================
"""

import torch
import torch.nn.functional as F
import numpy as np
import pandas as pd

from ml.space.base import Fabric


class RPulsarCore(Fabric):
    """
    Core evolutionary neural engine responsible for population management,
    neural computation, and genetic evolution.

    This class encapsulates all heavy tensor operations and evolutionary
    mechanics used to optimize feature combinations and neural weights
    simultaneously.
    """

    def __init__(self, config, device, seed=42):
        self.config = config
        self.device = device
        self.seed = seed

        # Extract core hyperparameters from configuration.
        self.pop_size = int(self.config.get('population_size', 1200))
        self.gene_count = int(self.config.get('gene_count', 16))
        self.hidden_dim = int(self.config.get('hidden_dim', 128))
        self.initial_bias = float(self.config.get('initial_bias', -2.0))
        self.weight_mutation_rate = float(self.config.get("weight_mutation_rate", 0.005))
        self.verbose = bool(self.config.get("verbose", True))
        self.lookback = int(self.config.get('lookback', 24))

        # CNN Architectural parameters
        # Kernel size limits how many candles the Conv1D looks at per step.
        self.kernel_size = min(int(self.config.get('kernel_size', 5)), self.lookback)
        if self.kernel_size < 1: self.kernel_size = 1
        
        self.pool_size = 2
        
        # Calculate resulting temporal dimensions after Conv and Pool
        self.l_out = self.lookback - self.kernel_size + 1
        self.l_out_pool = max(1, self.l_out // self.pool_size)
        self.flatten_dim = self.hidden_dim * self.l_out_pool

        # Torch random generators
        self.torch_generator = torch.Generator(device='cpu').manual_seed(self.seed)
        if self.device.type == 'cuda':
            self.cuda_generator = torch.Generator(device=self.device).manual_seed(self.seed)
        else:
            self.cuda_generator = self.torch_generator

        # Evolutionary population state tensors.
        self.population = None
        self.thresholds = None
        self.pop_W1 = None
        self.pop_B1 = None
        self.pop_W2 = None
        self.pop_B2 = None

        # Gene importance tracking statistics.
        self.gene_scores = None
        self.gene_usage = None
        self.feature_names = None

    def init_population(self, num_indicators: int, feature_names: list):
        """
        Initialize the evolutionary population and neural weights.
        """
        self.feature_names = feature_names

        # Generate random gene selections for each individual.
        self.population = torch.stack([
            torch.tensor(
                np.random.choice(num_indicators, self.gene_count, replace=False),
                device=self.device
            )
            for _ in range(self.pop_size)
        ]).long()

        # W1 represents the 1D Convolutional filters for each individual.
        # Shape: (Population, Filters, Channels (Genes), Kernel_Size)
        self.pop_W1 = (
            torch.randn(self.pop_size, self.hidden_dim, self.gene_count, self.kernel_size, device=self.device)
            * np.sqrt(2.0 / (self.gene_count * self.kernel_size))
        )

        # Conv1D Bias
        self.pop_B1 = torch.zeros(self.pop_size, self.hidden_dim, device=self.device)

        # Output Dense layer mapping the pooled chronological features to a single logit.
        self.pop_W2 = (
            torch.randn(self.pop_size, self.flatten_dim, 1, device=self.device)
            * np.sqrt(2.0 / self.flatten_dim)
        )

        # Output bias initialized using the YAML configured value
        self.pop_B2 = torch.full((self.pop_size, 1, 1), self.initial_bias, device=self.device)

        # Per-individual classification thresholds.
        self.thresholds = torch.full((self.pop_size,), 0.40, device=self.device)

        # Global feature statistics
        self.gene_scores = torch.zeros(num_indicators, device=self.device)
        self.gene_usage = torch.zeros(num_indicators, device=self.device)

    def forward(self, x, w1, b1, w2, b2):
        """
        Execute the 1D-CNN forward pass for a batch of individuals.
        Uses grouped convolutions to process the entire population batch in parallel.

        Args:
            x (torch.Tensor): Flattened input from orchestrator (Chunk_Size, Num_Windows, Gene_Count * Lookback)
        """
        chunk_size, num_windows, _ = x.shape

        # Unflatten the input to restore chronological sequence
        # Shape: (Chunk_Size, Num_Windows, Gene_Count, Lookback)
        x_unflat = x.view(chunk_size, num_windows, self.gene_count, self.lookback)

        # Permute for Grouped Convolution: (Num_Windows, Chunk_Size * Gene_Count, Lookback)
        x_conv = x_unflat.permute(1, 0, 2, 3).reshape(num_windows, chunk_size * self.gene_count, self.lookback)

        # Reshape Conv filters for grouping: (Chunk_Size * Hidden_Dim, Gene_Count, Kernel_Size)
        w1_conv = w1.view(chunk_size * self.hidden_dim, self.gene_count, self.kernel_size)
        b1_conv = b1.view(chunk_size * self.hidden_dim)

        # Apply 1D Convolution over the chronological sequence
        # Output: (Num_Windows, Chunk_Size * Hidden_Dim, L_out)
        conv_out = F.conv1d(x_conv, w1_conv, bias=b1_conv, groups=chunk_size)

        # Apply GELU activation
        h1 = F.gelu(conv_out)

        # Apply 1D Max Pooling to extract dominant structural features across time
        # Output: (Num_Windows, Chunk_Size * Hidden_Dim, L_out_pool)
        h1_pool = F.max_pool1d(h1, kernel_size=self.pool_size)

        # Reshape back to individual networks for the final Dense layer
        # Shape: (Chunk_Size, Num_Windows, Hidden_Dim * L_out_pool)
        h1_reshaped = h1_pool.view(num_windows, chunk_size, self.hidden_dim, self.l_out_pool)
        h1_dense_input = h1_reshaped.permute(1, 0, 2, 3).reshape(chunk_size, num_windows, self.flatten_dim)

        # Final linear projection producing a single logit output
        return torch.bmm(h1_dense_input, w2) + b2

    def evolve(self, latest_f1, latest_score):
        """
        Apply evolutionary operators to produce the next generation.
        Crossover specifically swaps Conv1D filters at the gene level.
        """
        f1_scores = latest_f1.to(self.device).flatten()
        primary_scores = latest_score.to(self.device).flatten()

        # Identify champion
        gen_best_f1_val, gen_best_f1_idx = torch.max(f1_scores, dim=0)

        # Clone champion state
        champ_pop = self.population[gen_best_f1_idx].clone()
        champ_w1 = self.pop_W1[gen_best_f1_idx].clone()
        champ_b1 = self.pop_B1[gen_best_f1_idx].clone()
        champ_w2 = self.pop_W2[gen_best_f1_idx].clone()
        champ_b2 = self.pop_B2[gen_best_f1_idx].clone()
        champ_thresh = self.thresholds[gen_best_f1_idx].clone()

        # Sort population
        idx = torch.argsort(primary_scores, descending=True)
        self.population = self.population[idx]
        self.thresholds = self.thresholds[idx]
        self.pop_W1, self.pop_B1 = self.pop_W1[idx], self.pop_B1[idx]
        self.pop_W2, self.pop_B2 = self.pop_W2[idx], self.pop_B2[idx]

        keep = max(2, self.pop_size // 10)

        # Buffers for next generation
        new_pop = self.population.clone()
        new_w1, new_b1 = self.pop_W1.clone(), self.pop_B1.clone()
        new_w2, new_b2 = self.pop_W2.clone(), self.pop_B2.clone()
        new_thresh = self.thresholds.clone()

        # Anchor champion
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
                # Crossover Genes
                cut = torch.randint(0, self.gene_count, (1,), generator=self.torch_generator).item()
                child_genes = torch.cat([self.population[p1, :cut], self.population[p2, cut:]])
                
                # Crossover Conv Filters exactly along the Gene channel dimension (dim=1)
                child_w1 = torch.cat([
                    self.pop_W1[p1, :, :cut, :], 
                    self.pop_W1[p2, :, cut:, :]
                ], dim=1)

                alpha = torch.rand(1, device=self.device, generator=self.cuda_generator) * 0.2 + 0.4
                child_b1 = alpha * self.pop_B1[p1] + (1 - alpha) * self.pop_B1[p2]

                unique_genes = torch.unique(child_genes)

                if len(unique_genes) < self.gene_count:
                    used_mask = torch.zeros(len(self.feature_names), dtype=torch.bool, device=self.device)
                    used_mask[unique_genes] = True
                    available = torch.where(~used_mask)[0]

                    needed = self.gene_count - len(unique_genes)
                    perm = torch.randperm(len(available), generator=self.torch_generator)[:needed]
                    new_genes = available[perm]

                    final_genes = torch.cat([unique_genes, new_genes])

                    # Initialize fresh Conv weights
                    final_w1 = torch.randn(
                        (self.hidden_dim, self.gene_count, self.kernel_size),
                        device=self.device
                    ) * 0.01

                    for j, gene in enumerate(unique_genes):
                        pos = torch.where(child_genes == gene)[0][0]
                        final_w1[:, j, :] = child_w1[:, pos, :]

                else:
                    final_genes = child_genes
                    final_w1 = child_w1

                new_pop[i] = final_genes
                new_w1[i] = final_w1
                new_b1[i] = child_b1

                new_w2[i] = alpha * self.pop_W2[p1] + (1 - alpha) * self.pop_W2[p2]
                new_b2[i] = alpha * self.pop_B2[p1] + (1 - alpha) * self.pop_B2[p2]
                new_thresh[i] = alpha * self.thresholds[p1] + (1 - alpha) * self.thresholds[p2]

            else:
                # Mutation
                child_genes = self.population[p1].clone()
                child_w1 = self.pop_W1[p1].clone()
                child_b1 = self.pop_B1[p1].clone()

                if torch.rand(1, generator=self.torch_generator).item() < 0.3:
                    n_mutations = torch.randint(1, min(4, self.gene_count), (1,), generator=self.torch_generator).item()
                    for _ in range(n_mutations):
                        used_mask = torch.zeros(len(self.feature_names), dtype=torch.bool, device=self.device)
                        used_mask[child_genes] = True
                        available = torch.where(~used_mask)[0]

                        if len(available) > 0:
                            pos = torch.randint(0, self.gene_count, (1,), generator=self.torch_generator).item()
                            new_gene = available[torch.randint(0, len(available), (1,), generator=self.torch_generator)].item()
                            child_genes[pos] = new_gene
                            
                            # Mutate specific filter bank
                            child_w1[:, pos, :] = torch.randn(
                                (self.hidden_dim, self.kernel_size),
                                device=self.device
                            ) * 0.01

                new_pop[i] = child_genes
                new_w1[i] = child_w1 + torch.randn_like(child_w1) * mutation_std
                new_b1[i] = child_b1 + torch.randn_like(child_b1) * mutation_std * 0.1
                new_w2[i] = self.pop_W2[p1] + torch.randn_like(self.pop_W2[p1]) * mutation_std
                new_b2[i] = self.pop_B2[p1] + torch.randn_like(self.pop_B2[p1]) * mutation_std * 0.1

                new_thresh[i] = self.thresholds[p1] + torch.randn(1, device=self.device, generator=self.cuda_generator).squeeze() * 0.01

        self.population = new_pop
        self.pop_W1, self.pop_B1 = new_w1, new_b1
        self.pop_W2, self.pop_B2 = new_w2, new_b2
        self.thresholds = torch.clamp(new_thresh, 0.10, 0.85)

    def run_atomic_scan(self):
        """
        Repopulate weakest individuals with fresh Conv1D architecture.
        """
        vitality = (self.gene_scores + 0.1) / (self.gene_usage + 1.0)
        pool_size = max(int(self.gene_count * 1.5), 40)
        pool_size = min(pool_size, len(self.feature_names))
        pool = torch.argsort(vitality, descending=True)[:pool_size]

        start_idx = int(self.pop_size * 0.8)
        for i in range(start_idx, self.pop_size):
            self.population[i] = pool[torch.randperm(len(pool), generator=self.torch_generator)[:self.gene_count]].to(self.device)

            self.pop_W1[i] = (
                torch.randn(
                    self.hidden_dim, self.gene_count, self.kernel_size,
                    device=self.device, generator=self.cuda_generator
                ) * np.sqrt(2.0 / (self.gene_count * self.kernel_size))
            )
            self.pop_B1[i] = 0.0

            self.pop_W2[i] = (
                torch.randn(
                    self.flatten_dim, 1,
                    device=self.device, generator=self.cuda_generator
                ) * np.sqrt(2.0 / self.flatten_dim)
            )
            self.pop_B2[i] = self.initial_bias

    def emit(self, features: pd.DataFrame) -> np.ndarray:
        """
        Perform 1D-CNN inference and return un-smoothed, raw probabilities.
        """
        if len(features) < self.lookback:
            return np.array([0.0] * len(features))

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

            # Return raw, natural probabilities (EMA removed)
            probs = torch.sigmoid(logits).cpu().numpy().flatten()
            padding = np.array([0.0] * (self.lookback - 1))

            return np.concatenate([padding, probs])