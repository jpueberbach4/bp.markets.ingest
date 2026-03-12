"""
===============================================================================
File:        rpulsar_core2.py
Author:      JP Ueberbach
Created:     2026-03-12
Revision:    Native PyTorch Rough Path Engine (Auto-Tuning Physics)

Description:
    Evolutionary neural feature-selection and signal-emission engine.

    This module implements a hybrid evolutionary optimization framework
    designed to discover high-value feature combinations and neural decision
    boundaries within large indicator spaces.

    *AUTO-TUNING UPDATE*: The environment's physics (Silent Bias, Quiet Zone 
    Floor, and Penalty Coefficient) are no longer global magic numbers. They 
    are now embedded directly into the genome of each individual. The engine 
    will automatically evolve the perfect Signal-to-Noise Ratio (SNR) and 
    conviction thresholds specific to the selected genes.

    *ROUGH PATH UPDATE*: This engine computes the Depth-2 Log-Signature
    using pure, native PyTorch tensor operations. It mathematically extracts
    the Lead-Lag Levy Area (cross-terms) without relying on external C++ 
    libraries like `signatory` or `roughpy`, ensuring maximum CUDA throughput
    and zero installation friction.

    Each individual in the population represents:
        • A sparse set of selected features ("genes")
        • A lightweight neural network operating on the Log-Signature
        • A signal threshold used for classification
        • An individualized physics profile (Bias, Penalty Coeff, Silence Floor)

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
    Includes Auto-Tuning Environmental Physics.
    """

    def __init__(self, config, device, seed=42):
        self.config = config
        self.device = device
        self.seed = seed

        # Meta-hyperparameters
        self.pop_size = int(self.config.get('population_size', 1200))
        self.gene_count = int(self.config.get('gene_count', 16))
        self.hidden_dim = int(self.config.get('hidden_dim', 128))
        self.weight_mutation_rate = float(self.config.get("weight_mutation_rate", 0.005))
        self.lookback = int(self.config.get('lookback', 4))
        self.verbose = bool(self.config.get("verbose", True))

        # Rough Path Theory dimensions (Native Depth 2)
        self.sig_depth = 2 
        
        # Depth 1 = gene_count
        # Depth 2 = (gene_count * (gene_count - 1)) / 2  (Skew-symmetric upper triangle)
        self.sig_channels = self.gene_count + (self.gene_count * (self.gene_count - 1)) // 2
        
        # Input Dim = Log-Signature + Basepoint
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

        # State Tensors (Neural & Genetic)
        self.population = None
        self.thresholds = None
        self.pop_W1 = None
        self.pop_B1 = None
        self.pop_W2 = None
        self.pop_B2 = None
        
        # State Tensors (Auto-Tuning Environmental Physics)
        self.pop_silence_floor = None 
        self.pop_penalty_coeff = None 
        
        # Vitality tracking
        self.gene_scores = None
        self.gene_usage = None
        self.feature_names = None
        
        # Cache triu indices for fast Levy area extraction
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

        # Weight Initialization (Kaiming scaled for features)
        self.pop_W1 = (
            torch.randn(self.pop_size, self.input_dim, self.hidden_dim, device=self.device)
            * np.sqrt(2.0 / self.input_dim)
        )
        self.pop_B1 = torch.zeros(self.pop_size, 1, self.hidden_dim, device=self.device)
        self.pop_W2 = (
            torch.randn(self.pop_size, self.hidden_dim, 1, device=self.device)
            * np.sqrt(2.0 / self.hidden_dim)
        )

        # --- AUTO-TUNING INITIALIZATION ---
        # pop_B2 (Silent Bias): Initialized uniformly between -12.0 and -2.0
        self.pop_B2 = torch.distributions.Uniform(-12.0, -2.0).sample((self.pop_size, 1, 1)).to(self.device)
        
        # pop_silence_floor (Quiet Zone Hinge): Initialized between 4.0 and 12.0
        self.pop_silence_floor = torch.distributions.Uniform(4.0, 12.0).sample((self.pop_size,)).to(self.device)
        
        # pop_penalty_coeff (Punishment Weight): Initialized between 0.01 and 0.1
        self.pop_penalty_coeff = torch.distributions.Uniform(0.01, 0.1).sample((self.pop_size,)).to(self.device)
        
        # Thresholds: Broad distribution to allow different confidence intervals
        self.thresholds = torch.distributions.Uniform(0.20, 0.80).sample((self.pop_size,)).to(self.device)

        self.gene_scores = torch.zeros(num_indicators, device=self.device)
        self.gene_usage = torch.zeros(num_indicators, device=self.device)

    def compute_native_logsig(self, path):
        """
        Computes the Depth-2 Log-Signature entirely within PyTorch.
        Path shape expected: (Batch, Time, Channels)
        """
        # 1. Depth 1: The simple path increment
        depth_1 = path[:, -1, :] - path[:, 0, :]
        
        # 2. Depth 2: The Levy Area (Iterated Cross-Integrals)
        X_t = path[:, :-1, :]
        X_t_plus_1 = path[:, 1:, :]
        
        cross = torch.einsum('bti,btj->bij', X_t, X_t_plus_1) - torch.einsum('bti,btj->bij', X_t_plus_1, X_t)
        area = 0.5 * cross
        
        # Flatten only the upper triangle
        depth_2 = area[:, self.triu_idx[0], self.triu_idx[1]]
        
        return torch.cat([depth_1, depth_2], dim=1)

    def forward(self, x, w1, b1, w2, b2):
        """
        Execute the neural forward pass using Native Log-Signatures.
        """
        B, T, _ = x.shape

        path = x.view(B * T, self.gene_count, self.lookback).transpose(1, 2)
        logsig = self.compute_native_logsig(path)
        basepoint = path[:, -1, :]

        features = torch.cat([logsig, basepoint], dim=1)
        features = features.view(B, T, self.input_dim)

        h1 = torch.bmm(features, w1)
        h1 = F.leaky_relu(h1 + b1, negative_slope=0.01)
        
        # b2 is now individualized per population member
        return torch.bmm(h1, w2) + b2

    def evolve(self, latest_f1, latest_score):
        """
        Applies survival of the fittest to weights, genes, AND auto-tuning physics.
        """
        f1_scores = latest_f1.to(self.device).flatten()
        primary_scores = latest_score.to(self.device).flatten()

        gen_best_f1_val, gen_best_f1_idx = torch.max(f1_scores, dim=0)

        # Clone champion traits to preserve exact state
        champ_pop = self.population[gen_best_f1_idx].clone()
        champ_w1 = self.pop_W1[gen_best_f1_idx].clone()
        champ_b1 = self.pop_B1[gen_best_f1_idx].clone()
        champ_w2 = self.pop_W2[gen_best_f1_idx].clone()
        champ_b2 = self.pop_B2[gen_best_f1_idx].clone()
        champ_thresh = self.thresholds[gen_best_f1_idx].clone()
        champ_floor = self.pop_silence_floor[gen_best_f1_idx].clone()
        champ_coeff = self.pop_penalty_coeff[gen_best_f1_idx].clone()

        # Sort entire population by main fitness score
        idx = torch.argsort(primary_scores, descending=True)

        self.population = self.population[idx]
        self.pop_W1, self.pop_B1 = self.pop_W1[idx], self.pop_B1[idx]
        self.pop_W2, self.pop_B2 = self.pop_W2[idx], self.pop_B2[idx]
        self.thresholds = self.thresholds[idx]
        self.pop_silence_floor = self.pop_silence_floor[idx]
        self.pop_penalty_coeff = self.pop_penalty_coeff[idx]

        keep = max(2, self.pop_size // 10)

        new_pop = self.population.clone()
        new_w1, new_b1 = self.pop_W1.clone(), self.pop_B1.clone()
        new_w2, new_b2 = self.pop_W2.clone(), self.pop_B2.clone()
        new_thresh = self.thresholds.clone()
        new_silence = self.pop_silence_floor.clone()
        new_p_coeff = self.pop_penalty_coeff.clone()

        # Enforce Elitism (Quantum Lock)
        new_pop[1] = champ_pop
        new_w1[1], new_b1[1] = champ_w1, champ_b1
        new_w2[1], new_b2[1] = champ_w2, champ_b2
        new_thresh[1] = champ_thresh
        new_silence[1] = champ_floor
        new_p_coeff[1] = champ_coeff

        if self.verbose:
            self.print("CORE_QUANTUM_LOCK", f1=gen_best_f1_val.item())

        std = self.weight_mutation_rate

        for i in range(keep, self.pop_size):
            p1, p2 = torch.randint(0, keep, (2,), generator=self.torch_generator)

            if torch.rand(1, generator=self.torch_generator).item() < 0.7:
                # --- CROSSOVER ---
                cut = torch.randint(0, self.gene_count, (1,), generator=self.torch_generator).item()
                child_genes = torch.cat([self.population[p1, :cut], self.population[p2, cut:]])
                
                alpha = torch.rand(1, device=self.device, generator=self.cuda_generator)
                
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

                # Reset W1 because Lie Algebra topology changes entirely with new genes
                final_w1 = torch.randn((self.input_dim, self.hidden_dim), device=self.device) * np.sqrt(2.0 / self.input_dim)

                new_pop[i] = final_genes
                new_w1[i] = final_w1
                
                # Blend Biases, Weights, and Physics
                new_b1[i] = alpha * self.pop_B1[p1] + (1 - alpha) * self.pop_B1[p2]
                new_w2[i] = alpha * self.pop_W2[p1] + (1 - alpha) * self.pop_W2[p2]
                new_b2[i] = alpha * self.pop_B2[p1] + (1 - alpha) * self.pop_B2[p2]
                new_thresh[i] = alpha * self.thresholds[p1] + (1 - alpha) * self.thresholds[p2]
                
                new_silence[i] = alpha * self.pop_silence_floor[p1] + (1 - alpha) * self.pop_silence_floor[p2]
                new_p_coeff[i] = alpha * self.pop_penalty_coeff[p1] + (1 - alpha) * self.pop_penalty_coeff[p2]

            else:
                # --- MUTATION ---
                child_genes = self.population[p1].clone()
                child_w1 = self.pop_W1[p1].clone()
                
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

                    # Gene topology mutated, must reset W1 mapping
                    child_w1 = torch.randn((self.input_dim, self.hidden_dim), device=self.device) * np.sqrt(2.0 / self.input_dim)

                new_pop[i] = child_genes
                new_w1[i] = child_w1 + torch.randn_like(child_w1) * std
                new_b1[i] = self.pop_B1[p1] + torch.randn_like(self.pop_B1[p1]) * std * 0.1
                new_w2[i] = self.pop_W2[p1] + torch.randn_like(self.pop_W2[p1]) * std
                new_b2[i] = self.pop_B2[p1] + torch.randn_like(self.pop_B2[p1]) * std * 0.1
                new_thresh[i] = self.thresholds[p1] + torch.randn(1, device=self.device, generator=self.cuda_generator).squeeze() * 0.02
                
                # Mutate the Physics Constraints
                new_silence[i] = self.pop_silence_floor[p1] + torch.randn(1, device=self.device).squeeze() * std * 2.0
                new_p_coeff[i] = self.pop_penalty_coeff[p1] + torch.randn(1, device=self.device).squeeze() * std * 0.1

        # Apply state and clamp bounds to prevent mathematical runaway
        self.population = new_pop
        self.pop_W1, self.pop_B1 = new_w1, new_b1
        self.pop_W2, self.pop_B2 = new_w2, new_b2
        
        self.thresholds = torch.clamp(new_thresh, 0.10, 0.90)
        self.pop_silence_floor = torch.clamp(new_silence, 2.0, 15.0)
        self.pop_penalty_coeff = torch.clamp(new_p_coeff, 0.001, 0.5)

    def diagnostic(self, x, w1, b1, w2, b2):
        """
        Native Diagnostic tool. 
        Intercepts the actual forward pass logic of RPulsarCore2.
        """
        with torch.no_grad():
            B, T, _ = x.shape
            path = x.view(B * T, self.gene_count, self.lookback).transpose(1, 2)

            logsig = self.compute_native_logsig(path)
            basepoint = path[:, -1, :]
            
            features = torch.cat([logsig, basepoint], dim=1)
            features_batched = features.view(B, T, self.input_dim)
            
            h1 = torch.bmm(features_batched, w1)
            h1 = F.gelu(h1 + b1)
            logits = torch.bmm(h1, w2) + b2

            print("\n" + "!"*60)
            print("NATIVE ROUGH PATH DIAGNOSTIC")
            print(f"Log-Signature Mean: {logsig.mean().item():.6f} | Std: {logsig.std().item():.6f}")
            print(f"Logits Mean:        {logits.mean().item():.6f} | Std: {logits.std().item():.6f}")
            print(f"Logits Max:         {logits.max().item():.6f}  | Min: {logits.min().item():.6f}")
            print("!"*60 + "\n")

    def run_atomic_scan(self):
        """
        Refreshes the bottom 20% of the population with high-vitality genes,
        and completely re-initializes their weights and physics.
        """
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
                torch.randn(self.input_dim, self.hidden_dim, device=self.device, generator=self.cuda_generator) 
                * np.sqrt(2.0 / self.input_dim)
            )
            self.pop_W2[i] = (
                torch.randn(self.hidden_dim, 1, device=self.device, generator=self.cuda_generator) 
                * np.sqrt(2.0 / self.hidden_dim)
            )
            
            # Completely reset physics for new entrants
            self.pop_B2[i] = torch.distributions.Uniform(-12.0, -2.0).sample().item()
            self.pop_silence_floor[i] = torch.distributions.Uniform(4.0, 12.0).sample().item()
            self.pop_penalty_coeff[i] = torch.distributions.Uniform(0.01, 0.1).sample().item()
            self.thresholds[i] = torch.distributions.Uniform(0.20, 0.80).sample().item()

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