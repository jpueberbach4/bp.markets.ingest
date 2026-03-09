"""
===============================================================================
File:        rpulsar_core.py
Author:      JP Ueberbach
Created:     2026-03-08
Revision:    Documentation expansion and inline comment clarification

Description:
    Evolutionary neural feature-selection and signal-emission engine.

    This module implements a hybrid evolutionary optimization framework
    designed to discover high-value feature combinations and neural decision
    boundaries within large indicator spaces.

    Each individual in the population represents:

        • A sparse set of selected features ("genes")
        • A lightweight neural network operating on those features
        • A signal threshold used for classification

    The system combines two optimization mechanisms:

        1. Gradient-based learning within individuals
        2. Genetic evolution across generations

    This hybrid approach allows the system to explore large feature spaces
    while maintaining adaptive learning dynamics.

Core Evolutionary Concepts:
    • Population-based search
    • Elitism (champion preservation)
    • Genetic crossover between individuals
    • Mutation of both genes and neural weights
    • Feature vitality tracking across generations

Neural Architecture:
    Each individual uses a lightweight feedforward network consisting of:

        Input:  Gene_Count × Lookback window
        Hidden: GELU activated dense layer
        Output: Single logit score

    The input layer effectively acts as a **spatio-temporal feature filter**
    capturing interactions between features across multiple time steps.

Signal Generation:
    Individuals emit binary signals using:

        sigmoid(logit) > threshold

    Thresholds evolve alongside the network weights.

Key Capabilities:
    • GPU-friendly batched population evaluation
    • Evolutionary feature selection
    • Temporal pattern recognition via sliding windows
    • Champion preservation across generations
    • Adaptive gene vitality scoring
    • Atomic reseeding of weak individuals

Primary Component:
    RPulsarCore
        Handles population state, evolutionary operations, neural
        evaluation, and inference.

Requirements:
    • Python 3.8+
    • PyTorch
    • NumPy
    • Pandas

Notes:
    This is **research-grade experimental code** designed for evolutionary
    machine learning experimentation.

    Correct elite preservation and strict feature-weight alignment are
    essential. Subtle ordering bugs can significantly degrade performance.

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

    Attributes:
        config (dict): Runtime configuration dictionary.
        device (torch.device): CPU or CUDA device used for tensor operations.
        seed (int): Random seed used for deterministic behavior.

        pop_size (int): Number of individuals in the evolutionary population.
        gene_count (int): Number of features used per individual.
        hidden_dim (int): Size of the neural network hidden layer.

        population (torch.Tensor): Matrix storing feature indices per individual.
        thresholds (torch.Tensor): Classification threshold per individual.

        pop_W1 (torch.Tensor): First layer weight tensors per individual.
        pop_B1 (torch.Tensor): First layer bias tensors per individual.
        pop_W2 (torch.Tensor): Second layer weight tensors per individual.
        pop_B2 (torch.Tensor): Second layer bias tensors per individual.

        gene_scores (torch.Tensor): Running importance score for each feature.
        gene_usage (torch.Tensor): Count of how often each feature is used.

        lookback (int): Number of past timesteps used to construct temporal
            feature windows.
    """

    def __init__(self, config, device, seed=42):
        """
        Initialize the evolutionary core.

        Args:
            config (dict):
                Configuration dictionary containing evolutionary and neural
                hyperparameters.

            device (torch.device):
                Target device for tensor operations (CPU or CUDA).

            seed (int, optional):
                Random seed used to ensure reproducibility of evolutionary
                operations. Defaults to 42.
        """

        self.config = config
        self.device = device
        self.seed = seed

        # Extract core hyperparameters from configuration.
        # Defaults are used when parameters are not provided.
        self.pop_size = int(self.config.get('population_size', 1200))
        self.gene_count = int(self.config.get('gene_count', 16))
        self.hidden_dim = int(self.config.get('hidden_dim', 128))
        self.weight_mutation_rate = float(self.config.get("weight_mutation_rate", 0.005))
        self.verbose = bool(self.config.get("verbose", True))

        # Torch random generator used for CPU-based stochastic operations.
        # This ensures deterministic evolutionary behavior when a seed is set.
        self.torch_generator = torch.Generator(device='cpu').manual_seed(self.seed)

        # Separate generator for CUDA devices to maintain reproducibility
        # across GPU operations.
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

        # Human-readable feature names for debugging or diagnostics.
        self.feature_names = None

        # Number of timesteps used for temporal context.
        # Each gene contributes a full time window of features.
        self.lookback = int(self.config.get('lookback', 8))

    def init_population(self, num_indicators: int, feature_names: list):
        """
        Initialize the evolutionary population and neural weights.

        Each individual receives:
            • A random subset of features ("genes")
            • A randomly initialized neural network
            • A default classification threshold

        Args:
            num_indicators (int):
                Total number of available input features.

            feature_names (list):
                Human-readable feature names corresponding to indicators.
        """

        self.feature_names = feature_names

        # Generate random gene selections for each individual.
        # Each genome consists of `gene_count` unique feature indices.
        self.population = torch.stack([
            torch.tensor(
                np.random.choice(num_indicators, self.gene_count, replace=False),
                device=self.device
            )
            for _ in range(self.pop_size)
        ]).long()

        # First neural layer weights.
        # The input dimension equals Gene_Count × Lookback.
        # Each gene contributes a full temporal slice of inputs.
        self.pop_W1 = (
            torch.randn(self.pop_size, self.gene_count * self.lookback, self.hidden_dim, device=self.device)
            * np.sqrt(2.0 / (self.gene_count * self.lookback))
        )

        # Bias for the first hidden layer.
        self.pop_B1 = torch.zeros(self.pop_size, 1, self.hidden_dim, device=self.device)

        # Output layer weights mapping hidden features to a single logit.
        self.pop_W2 = (
            torch.randn(self.pop_size, self.hidden_dim, 1, device=self.device)
            * np.sqrt(2.0 / self.hidden_dim)
        )

        # Output bias initialized slightly negative to suppress early signals.
        self.pop_B2 = torch.full((self.pop_size, 1, 1), -2.0, device=self.device)

        # Per-individual classification thresholds.
        self.thresholds = torch.full((self.pop_size,), 0.40, device=self.device)

        # Global feature statistics used for vitality scoring.
        self.gene_scores = torch.zeros(num_indicators, device=self.device)
        self.gene_usage = torch.zeros(num_indicators, device=self.device)

    def forward(self, x, w1, b1, w2, b2):
        """
        Execute the neural forward pass for a batch of individuals.

        The model treats the flattened gene-time window as a temporal
        feature vector and applies a dense hidden transformation followed
        by a final linear output layer.

        Args:
            x (torch.Tensor):
                Input tensor of shape:
                (Population_Chunk, Time_Steps, Gene_Count * Lookback)

            w1 (torch.Tensor):
                First-layer weights.

            b1 (torch.Tensor):
                First-layer bias.

            w2 (torch.Tensor):
                Second-layer weights.

            b2 (torch.Tensor):
                Second-layer bias.

        Returns:
            torch.Tensor:
                Logit predictions for each timestep.
        """

        # Compute hidden representation via batched matrix multiplication.
        h1 = torch.bmm(x, w1)

        # Apply GELU activation after adding bias.
        h1 = F.gelu(h1 + b1)

        # Final linear projection producing a single logit output.
        return torch.bmm(h1, w2) + b2

    def evolve(self, latest_f1, latest_score):
        """
        Apply evolutionary operators to produce the next generation.

        Evolution consists of:

            1. Champion preservation (elitism)
            2. Population ranking
            3. Crossover between strong individuals
            4. Random mutation of genes and weights

        Feature–weight alignment is strictly preserved to ensure that
        neural weights remain associated with their corresponding genes.

        Args:
            latest_f1 (torch.Tensor):
                F1 scores for each individual.

            latest_score (torch.Tensor):
                Primary evolutionary fitness metric.
        """

        f1_scores = latest_f1.to(self.device).flatten()
        primary_scores = latest_score.to(self.device).flatten()

        # Identify the best-performing individual based on F1 score.
        gen_best_f1_val, gen_best_f1_idx = torch.max(f1_scores, dim=0)

        # Clone the champion's full neural state to ensure preservation.
        champ_pop = self.population[gen_best_f1_idx].clone()
        champ_w1 = self.pop_W1[gen_best_f1_idx].clone()
        champ_b1 = self.pop_B1[gen_best_f1_idx].clone()
        champ_w2 = self.pop_W2[gen_best_f1_idx].clone()
        champ_b2 = self.pop_B2[gen_best_f1_idx].clone()
        champ_thresh = self.thresholds[gen_best_f1_idx].clone()

        # Sort the entire population by evolutionary score.
        idx = torch.argsort(primary_scores, descending=True)

        self.population = self.population[idx]
        self.thresholds = self.thresholds[idx]
        self.pop_W1, self.pop_B1 = self.pop_W1[idx], self.pop_B1[idx]
        self.pop_W2, self.pop_B2 = self.pop_W2[idx], self.pop_B2[idx]

        # Number of individuals preserved for breeding.
        keep = max(2, self.pop_size // 10)

        # Allocate buffers for the next generation.
        new_pop = self.population.clone()
        new_w1, new_b1 = self.pop_W1.clone(), self.pop_B1.clone()
        new_w2, new_b2 = self.pop_W2.clone(), self.pop_B2.clone()
        new_thresh = self.thresholds.clone()

        # Explicitly anchor the champion into the next generation.
        new_pop[1] = champ_pop
        new_w1[1], new_b1[1] = champ_w1, champ_b1
        new_w2[1], new_b2[1] = champ_w2, champ_b2
        new_thresh[1] = champ_thresh

        if self.verbose:
            self.print("CORE_QUANTUM_LOCK", f1=gen_best_f1_val.item())

        mutation_std = self.weight_mutation_rate

        # Iterate through individuals that will be replaced by offspring.
        for i in range(keep, self.pop_size):

            # Randomly select two parents from the elite pool.
            p1, p2 = torch.randint(0, keep, (2,), generator=self.torch_generator)

            # Decide whether crossover or mutation will occur.
            if torch.rand(1, generator=self.torch_generator).item() < 0.7:

                # Select gene crossover position.
                cut = torch.randint(0, self.gene_count, (1,), generator=self.torch_generator).item()

                # Convert gene cut to weight cut (accounting for lookback window).
                w1_cut = cut * self.lookback

                # Combine genes and corresponding weight segments.
                child_genes = torch.cat([self.population[p1, :cut], self.population[p2, cut:]])
                child_w1 = torch.cat([self.pop_W1[p1, :w1_cut], self.pop_W1[p2, w1_cut:]])

                # Blend biases and output layer parameters.
                alpha = torch.rand(1, device=self.device, generator=self.cuda_generator) * 0.2 + 0.4
                child_b1 = alpha * self.pop_B1[p1] + (1 - alpha) * self.pop_B1[p2]

                # Ensure genes remain unique.
                unique_genes = torch.unique(child_genes)

                if len(unique_genes) < self.gene_count:

                    # Identify unused features.
                    used_mask = torch.zeros(len(self.feature_names), dtype=torch.bool, device=self.device)
                    used_mask[unique_genes] = True
                    available = torch.where(~used_mask)[0]

                    needed = self.gene_count - len(unique_genes)

                    perm = torch.randperm(len(available), generator=self.torch_generator)[:needed]
                    new_genes = available[perm]

                    final_genes = torch.cat([unique_genes, new_genes])

                    # Initialize fresh weights for repaired genome.
                    final_w1 = torch.randn(
                        (self.gene_count * self.lookback, self.hidden_dim),
                        device=self.device
                    ) * 0.01

                    # Copy correct weights for surviving genes.
                    for j, gene in enumerate(unique_genes):

                        pos = torch.where(child_genes == gene)[0][0]

                        j_start = j * self.lookback
                        j_end = (j + 1) * self.lookback

                        pos_start = pos * self.lookback
                        pos_end = (pos + 1) * self.lookback

                        final_w1[j_start:j_end] = child_w1[pos_start:pos_end]

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

                # Mutation path: clone parent and apply noise.
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

                            pos_start = pos * self.lookback
                            pos_end = (pos + 1) * self.lookback

                            child_w1[pos_start:pos_end] = torch.randn(
                                (self.lookback, self.hidden_dim),
                                device=self.device
                            ) * 0.01

                new_pop[i] = child_genes

                new_w1[i] = child_w1 + torch.randn_like(child_w1) * mutation_std
                new_b1[i] = child_b1 + torch.randn_like(child_b1) * mutation_std * 0.1

                new_w2[i] = self.pop_W2[p1] + torch.randn_like(self.pop_W2[p1]) * mutation_std
                new_b2[i] = self.pop_B2[p1] + torch.randn_like(self.pop_B2[p1]) * mutation_std * 0.1

                new_thresh[i] = self.thresholds[p1] + torch.randn(
                    1,
                    device=self.device,
                    generator=self.cuda_generator
                ).squeeze() * 0.01

        # Apply final population updates.
        self.population = new_pop
        self.pop_W1, self.pop_B1 = new_w1, new_b1
        self.pop_W2, self.pop_B2 = new_w2, new_b2

        # Clamp thresholds to safe operating range.
        self.thresholds = torch.clamp(new_thresh, 0.10, 0.85)

    def run_atomic_scan(self):
        """
        Repopulate the weakest portion of the population.

        This mechanism injects new individuals built from the most
        promising genes according to historical vitality scores.

        The goal is to prevent stagnation and reintroduce strong
        genetic building blocks into underperforming individuals.
        """

        vitality = (self.gene_scores + 0.1) / (self.gene_usage + 1.0)

        pool_size = max(int(self.gene_count * 1.5), 40)
        pool_size = min(pool_size, len(self.feature_names))

        pool = torch.argsort(vitality, descending=True)[:pool_size]

        assert len(pool) == len(torch.unique(pool)), "Vitality pool contains duplicates!"

        start_idx = int(self.pop_size * 0.8)

        for i in range(start_idx, self.pop_size):

            # Randomly sample strong genes from the vitality pool.
            self.population[i] = pool[
                torch.randperm(len(pool), generator=self.torch_generator)[:self.gene_count]
            ].to(self.device)

            # Reinitialize neural weights for the new individual.
            self.pop_W1[i] = (
                torch.randn(
                    self.gene_count * self.lookback,
                    self.hidden_dim,
                    device=self.device,
                    generator=self.cuda_generator
                )
                * np.sqrt(2.0 / (self.gene_count * self.lookback))
            )

            self.pop_W2[i] = (
                torch.randn(
                    self.hidden_dim,
                    1,
                    device=self.device,
                    generator=self.cuda_generator
                )
                * np.sqrt(2.0 / self.hidden_dim)
            )

            # Reset output bias.
            self.pop_B2[i] = -2.0

    def emit(self, features: pd.DataFrame) -> np.ndarray:
        """
        Perform inference using the best individual in the population.

        The method constructs sliding temporal windows over the input
        feature matrix and evaluates them using the champion network.

        Args:
            features (pd.DataFrame):
                DataFrame containing indicator values.

        Returns:
            np.ndarray:
                Boolean prediction vector aligned with the input rows.
        """

        if len(features) < self.lookback:
            return np.array([False] * len(features))

        with torch.no_grad():

            x = torch.tensor(features.values.astype(np.float32), device=self.device)

            # Select only the champion's gene features.
            x_sel = x[:, self.population[0]]

            # Construct sliding temporal windows.
            windows = x_sel.unfold(dimension=0, size=self.lookback, step=1)

            # Flatten gene and time dimensions.
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