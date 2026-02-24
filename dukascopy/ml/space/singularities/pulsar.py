"""
===============================================================================
 File:        pulsar.py
 Author:      JP Ueberbach
 Created:     2026-02-23
              Elite preservation fix and evolutionary stability improvements

 Important:   This is RESEARCH-grade code. 

 Description:
      Evolutionary neural feature-selection and signal-emission engine.

      This module implements an evolutionary strategy over a population of
      lightweight neural networks, each operating on a sparse subset of
      features ("genes"). The system combines gradient-based learning within
      each generation with genetic operators across generations, enabling
      adaptive feature discovery, sparsity control, and robust signal
      generation.

      Core concepts:
        - Population-based evolution with elitism, crossover, and mutation
        - Per-individual neural networks trained via backpropagation
        - Dynamic feature (gene) selection and vitality scoring
        - Out-of-sample threshold optimization with density constraints
        - Atomic reseeding of weak individuals using high-impact genes

      Primary components:
        - PulsarSingularity:
            Orchestrates population initialization, training, evaluation,
            evolution, inference, and persistence. Includes Factory Spec
            global scale freezing for OOD inference parity.

      Key capabilities:
        - Chunked GPU-safe training over large populations
        - Precision-weighted F1 optimization with signal-density penalties
        - Long-term gene importance tracking with decay
        - Deterministic champion preservation and state export
        - Stateless inference via a single evolved individual

 Requirements:
      - Python 3.8+
      - PyTorch
      - NumPy
      - Pandas

 Notes:
      This system intentionally blends deterministic gradient descent with
      stochastic evolutionary pressure. Correct elite preservation is
      critical; subtle ordering bugs can materially degrade performance.
===============================================================================
"""
import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
import numpy as np
import pandas as pd
from typing import Optional

from ml.space.space import Singularity
from ml.space.lenses.spectograph import Spectrograph

class PulsarSingularity(Singularity):
    """
    1.4.8 Fix and polish: elite preservation fix. This is hard stuff. Brr
    Includes Factory Spec Global Physics locking.
    """
    def __init__(self, config):
        
        super().__init__(device=config.get('device'))
        self.config = config
        
        # setup
        self.pop_size = int(self.config.get('population_size', 1200))
        self.gene_count = int(self.config.get('gene_count', 16))
        self.hidden_dim = int(self.config.get('hidden_dim', 128))
        self.decay_factor = float(self.config.get('decay_factor', 0.9))
        self.chunk_size = int(self.config.get("gpu_chunk", 256))
        self.min_sigs = int(self.config.get("min_signals", 3))
        self.target_density = float(self.config.get("target_density", 0.01))
        self.precision_exp = float(self.config.get("precision_exp", 2.5))
        self.penalty_coeff = float(self.config.get("penalty_coeff", 1.0))
        self.thresh_steps = int(self.config.get("thresh_steps", 31))
        self.oos_boundary = float(self.config.get("oos_boundary", 0.75))
        self.epochs = int(self.config.get("epochs", 25))
        self.weight_mutation_rate = float(self.config.get("weight_mutation_rate", 0.005))
        self.verbose = bool(self.config.get("verbose", True))

        # FACTORY SPEC: Set random seeds for reproducibility
        self.seed = self.config.get('seed', 42)
        torch.manual_seed(self.seed)
        np.random.seed(self.seed)
        # FIXED: Create separate generators for CPU and CUDA operations
        self.torch_generator = torch.Generator(device='cpu').manual_seed(self.seed)
        if self.device.type == 'cuda':
            self.cuda_generator = torch.Generator(device=self.device).manual_seed(self.seed)
        else:
            self.cuda_generator = self.torch_generator

        # TODO: should use a lenses config in configuration
        self.spectrograph = Spectrograph(mode="focal", alpha=0.99, gamma=2.0)
        
        self.population = None  
        self.thresholds = None
        self.pop_W1 = None; self.pop_B1 = None
        self.pop_W2 = None; self.pop_B2 = None
        
        self.gene_scores = None
        self.gene_usage = None
        self.feature_names = None
        
        self.global_best_f1 = -1.0
        self.global_best_prec = 0.0  # Track best precision for tie-breaking
        self.latest_f1 = None
        self.latest_score = None
        self.latest_precision = None  # Track latest precision values

    def compress(self, universe):
        """Initializes population parameters and encodes universe data for training.

        This method extracts features and targets from the provided universe,
        converts them into GPU/CPU tensors, initializes a population of gene
        selections, and randomly initializes neural network weights and biases
        for each individual in the population.

        Args:
            universe: An object that provides a `bigbang()` method returning
                a feature DataFrame and a target Series.

        Side Effects:
            - Sets internal tensors for features, targets, population genes,
            neural network weights, biases, thresholds, and gene statistics.
            - Stores feature names and universe reference.
        """
        # Store universe reference for later use
        self.universe = universe

        # Extract feature matrix (DataFrame) and target vector (Series)
        feature_df, target_series = universe.bigbang()

        # Number of available indicators (features)
        num_indicators = len(feature_df.columns)

        # Cache feature names for interpretability/debugging
        self.feature_names = list(feature_df.columns)

        # Convert features to float32 NumPy array and replace NaNs/Infs with zeros
        vals = np.nan_to_num(feature_df.values.astype(np.float32))

        # Move feature matrix to torch tensor on the configured device
        self.lake = torch.tensor(vals, device=self.device)

        # Convert target series to tensor and reshape to (1, T, 1)
        self.y_all = torch.tensor(
            target_series.values.astype(np.float32),
            device=self.device
        ).view(1, -1, 1)

        # Initialize population genes:
        # each individual selects `gene_count` unique feature indices
        self.population = torch.stack([
            torch.tensor(
                np.random.choice(num_indicators, self.gene_count, replace=False),
                device=self.device
            )
            for _ in range(self.pop_size)
        ]).long()

        # Initialize first-layer weights using He initialization
        self.pop_W1 = (
            torch.randn(self.pop_size, self.gene_count, self.hidden_dim, device=self.device)
            * np.sqrt(2.0 / self.gene_count)
        )

        # Initialize first-layer biases to zero
        self.pop_B1 = torch.zeros(self.pop_size, 1, self.hidden_dim, device=self.device)

        # Initialize second-layer weights using He initialization
        self.pop_W2 = (
            torch.randn(self.pop_size, self.hidden_dim, 1, device=self.device)
            * np.sqrt(2.0 / self.hidden_dim)
        )

        # Initialize second-layer biases to a negative value (encourages sparsity)
        self.pop_B2 = torch.full((self.pop_size, 1, 1), -2.0, device=self.device)

        # Initialize decision thresholds for each individual
        self.thresholds = torch.full((self.pop_size,), 0.40, device=self.device)

        # Track cumulative importance score per gene
        self.gene_scores = torch.zeros(num_indicators, device=self.device)

        # Track how often each gene is selected across the population
        self.gene_usage = torch.zeros(num_indicators, device=self.device)

    def _forward(self, x, w1, b1, w2, b2):
        """Performs a forward pass through a two-layer neural network.

        This method applies a batched matrix multiplication for the first
        linear layer, followed by a GELU activation, and then applies a
        second linear transformation to produce the output.

        Args:
            x (torch.Tensor): Input tensor of shape (P, T, G), where:
                P = population size,
                T = time steps or samples,
                G = number of selected genes (features).
            w1 (torch.Tensor): First-layer weight tensor of shape
                (P, G, H), where H is the hidden dimension.
            b1 (torch.Tensor): First-layer bias tensor of shape
                (P, 1, H).
            w2 (torch.Tensor): Second-layer weight tensor of shape
                (P, H, 1).
            b2 (torch.Tensor): Second-layer bias tensor of shape
                (P, 1, 1).

        Returns:
            torch.Tensor: Output tensor of shape (P, T, 1) containing
            the model predictions for each population member.
        """
        # Apply first linear layer using batched matrix multiplication
        # Shape: (P, T, G) @ (P, G, H) -> (P, T, H)
        h1 = torch.bmm(x, w1)

        # Add bias and apply GELU nonlinearity
        h1 = F.gelu(h1 + b1)

        # Apply second linear layer to produce final output
        # Shape: (P, T, H) @ (P, H, 1) -> (P, T, 1)
        return torch.bmm(h1, w2) + b2

    def run_generation(self, config):
        """Runs one evolutionary generation over the population.

        This method:
            1. Splits data into in-sample (train) and out-of-sample (OOS).
            2. Trains each population member (in chunks) using backpropagation.
            3. Evaluates OOS performance across multiple probability thresholds.
            4. Selects the best threshold per individual based on a custom score.
            5. Updates gene importance statistics using performance-weighted attribution.
            6. Returns aggregated performance metrics including the 2D signal map.

        Args:
            config: Configuration object (currently unused but reserved
                for future extensibility).

        Returns:
            dict[str, torch.Tensor]: Dictionary containing concatenated tensors
            for the following metrics per population member:
                - "f1"
                - "sigs" (signal count)
                - "density"
                - "precision"
                - "recall"
                - "score"
                - "signal_map" (2D boolean tensor of locations)

        Side Effects:
            - Updates population weights and biases.
            - Updates gene importance and usage statistics.
            - Updates self.thresholds, self.latest_f1, and self.latest_score.
        """

        # Storage for metrics collected across all population chunks. Added signal_map.
        metrics = {"f1": [], "sigs": [], "density": [], "precision": [], "recall": [], "score": [], "signal_map": []}

        # Determine in-sample training cutoff index
        train_end = int(len(self.lake) * self.oos_boundary)

        # Apply decay to historical gene importance statistics
        self.gene_scores *= self.decay_factor
        self.gene_usage *= self.decay_factor

        # Iterate through population in memory-efficient chunks
        for i in range(0, self.pop_size, self.chunk_size):
            end_i = min(i + self.chunk_size, self.pop_size)
            curr_chunk = end_i - i

            # Selected gene indices for this chunk
            indices = self.population[i:end_i]

            # Prepare training features and targets
            # Shape after permute: (chunk, T, G)
            x_train = self.lake[:train_end, indices].permute(1, 0, 2)
            y_train = self.y_all[:, :train_end, :].expand(curr_chunk, -1, -1)

            # Clone weights/biases for gradient-based optimization
            w1 = self.pop_W1[i:end_i].detach().requires_grad_(True)
            b1 = self.pop_B1[i:end_i].detach().requires_grad_(True)
            w2 = self.pop_W2[i:end_i].detach().requires_grad_(True)
            b2 = self.pop_B2[i:end_i].detach().requires_grad_(True)

            optimizer = optim.Adam([w1, b1, w2, b2], lr=0.0005)

            # ----------------------
            # In-sample training
            # ----------------------
            for _ in range(self.epochs):
                optimizer.zero_grad()

                # Forward pass
                logits = self._forward(x_train, w1, b1, w2, b2)

                # Custom loss + sparsity penalty
                loss = (
                    self.spectrograph.analyze(logits, y_train)
                    + (torch.sigmoid(logits).mean() * self.penalty_coeff)
                )

                # Backpropagation
                loss.backward()

                # FIXED: Freeze champion individuals (indices 0 and 1) regardless of chunk
                # Find which individuals in this chunk are the top 2
                chunk_indices_global = torch.arange(i, end_i, device=self.device)
                elite_mask = (chunk_indices_global == 0) | (chunk_indices_global == 1)
                if elite_mask.any():
                    w1.grad[elite_mask] = 0
                    b1.grad[elite_mask] = 0
                    w2.grad[elite_mask] = 0
                    b2.grad[elite_mask] = 0

                # Gradient clipping for stability
                torch.nn.utils.clip_grad_norm_([w1, b1, w2, b2], max_norm=1.0)

                optimizer.step()

            # ----------------------
            # OOS Evaluation
            # ----------------------
            with torch.no_grad():

                # Persist trained weights back to population
                self.pop_W1[i:end_i].copy_(w1)
                self.pop_B1[i:end_i].copy_(b1)
                self.pop_W2[i:end_i].copy_(w2)
                self.pop_B2[i:end_i].copy_(b2)

                # Prepare OOS data
                x_oos = self.lake[train_end:, indices].permute(1, 0, 2)
                y_oos = self.y_all[:, train_end:, :].expand(curr_chunk, -1, -1)

                oos_target_count = y_oos[0].sum().item()

                # Convert logits to probabilities
                oos_probs = torch.sigmoid(self._forward(x_oos, w1, b1, w2, b2))

                # Initialize best metrics per individual
                best_score = torch.full((curr_chunk,), -1e9, device=self.device)
                best_f1 = torch.zeros(curr_chunk, device=self.device)
                best_thresh = torch.full((curr_chunk,), 0.40, device=self.device)
                best_sigs = torch.zeros(curr_chunk, device=self.device)
                best_prec = torch.zeros(curr_chunk, device=self.device)
                best_rec = torch.zeros(curr_chunk, device=self.device)
                
                # We also need to cache the exact sequence of predictions that generated the best score
                best_preds = torch.zeros_like(oos_probs, device=self.device)

                # Threshold sweep for optimal decision boundary
                for t in torch.linspace(0.15, 0.85, self.thresh_steps):

                    # Binary predictions at threshold t
                    preds = (oos_probs > t).float()

                    # Signal statistics
                    sig_count = preds.sum(dim=1).view(-1)
                    density = preds.mean(dim=1).view(-1)

                    # Confusion matrix components
                    tp = (preds * y_oos).sum(dim=1).view(-1)
                    fp = (preds * (1 - y_oos)).sum(dim=1).view(-1)
                    fn = ((1 - preds) * y_oos).sum(dim=1).view(-1)

                    # Precision, Recall, F1
                    prec = tp / (tp + fp + 1e-8)
                    rec = tp / (tp + fn + 1e-8)
                    f1 = 2 * prec * rec / (prec + rec + 1e-8)

                    # Custom score: F1 weighted by precision exponent
                    score = f1 * torch.clamp(torch.pow(prec, self.precision_exp), max=5.0)

                    # Density penalties
                    min_density = self.min_sigs / oos_probs.shape[1]
                    dev_high = torch.relu(density - self.target_density * 1.5) * 15.0
                    dev_low = torch.relu(min_density * 0.8 - density) * 6.0
                    score = score - (dev_high + dev_low)

                    # Enforce minimum signal constraint and precision floor
                    score = torch.where(
                        (sig_count >= self.min_sigs) & (prec > 0.02),
                        score,
                        torch.full_like(score, -1e9)
                    )

                    # Update best metrics where score improves
                    mask = score > best_score
                    best_score[mask] = score[mask]
                    best_f1[mask] = f1[mask]
                    best_thresh[mask] = t
                    best_sigs[mask] = sig_count[mask]
                    best_prec[mask] = prec[mask]
                    best_rec[mask] = rec[mask]
                    
                    # Capture the physical location of the signals for the diagnostic output
                    best_preds[mask] = preds[mask]

                # Optional logging
                if self.verbose:
                    print(
                        f"Chunk {i//self.chunk_size} | "
                        f"MaxP: {oos_probs.max():.3f} | "
                        f"Targets: {oos_target_count:.0f} | "
                        f"Fired: {best_sigs.max().item():.0f} | "
                        f"F1: {best_f1.max():.4f}"
                    )

                # Store optimal thresholds
                self.thresholds[i:end_i] = best_thresh

                # ----------------------
                # Gene importance update
                # ----------------------

                # Estimate gene contribution via |W1| x |W2|
                gene_imp = torch.bmm(w1.abs(), w2.abs()).squeeze(-1)

                # Normalize importance per individual
                imp_norm = gene_imp / (gene_imp.sum(dim=1, keepdim=True) + 1e-7)

                # Normalize scores across chunk for weighting
                score_range = best_score.max() - best_score.min()
                if score_range > 0.01:
                    norm_scores = (best_score - best_score.min()) / (score_range + 1e-8)
                else:
                    norm_scores = torch.ones_like(best_score)

                # Accumulate performance-weighted gene importance
                self.gene_scores.scatter_add_(
                    0,
                    indices.view(-1),
                    (imp_norm * norm_scores.view(-1, 1)).reshape(-1)
                )

                # Track gene usage frequency
                self.gene_usage.scatter_add_(
                    0,
                    indices.view(-1),
                    torch.ones(indices.numel(), device=self.device)
                )

                # Store metrics for aggregation
                metrics["f1"].append(best_f1.detach().cpu())
                metrics["sigs"].append(best_sigs.detach().cpu())
                metrics["density"].append((best_sigs / oos_probs.shape[1]).detach().cpu())
                metrics["precision"].append(best_prec.detach().cpu())
                metrics["recall"].append(best_rec.detach().cpu())
                metrics["score"].append(best_score.detach().cpu())
                metrics["signal_map"].append(best_preds.squeeze(-1).detach().cpu())

        # Concatenate chunk metrics into full population tensors
        res = {k: torch.cat(v) for k, v in metrics.items()}

        # Cache latest metrics
        self.latest_f1 = res["f1"].clone()
        self.latest_score = res["score"].clone()
        self.latest_precision = res["precision"].clone()  # NEW: Track precision

        # FIXED: Determine if we should save BEFORE updating global best
        gen_best_idx = torch.argmax(self.latest_f1).item()
        gen_best_f1 = self.latest_f1[gen_best_idx].item()
        gen_best_prec = self.latest_precision[gen_best_idx].item()
        
        # Check for improvement and set save flag
        self._pending_save = False
        if gen_best_f1 > self.global_best_f1:
            self._pending_save = True
            self._pending_save_idx = gen_best_idx
            self._pending_save_f1 = gen_best_f1
            self._pending_save_prec = gen_best_prec
            reason = f"new F1 record ({gen_best_f1:.4f} > {self.global_best_f1:.4f})"
            if self.verbose:
                print(f"🔥 [Evolution]: New High-Water Mark: {reason}")
        elif gen_best_f1 == self.global_best_f1 and gen_best_f1 > 0 and gen_best_prec > self.global_best_prec:
            self._pending_save = True
            self._pending_save_idx = gen_best_idx
            self._pending_save_f1 = gen_best_f1
            self._pending_save_prec = gen_best_prec
            reason = f"same F1 ({gen_best_f1:.4f}) but better precision ({gen_best_prec:.4f} > {self.global_best_prec:.4f})"
            if self.verbose:
                print(f"🔥 [Evolution]: New High-Water Mark: {reason}")
        
        # Update global best AFTER setting save flag
        if gen_best_f1 > self.global_best_f1:
            self.global_best_f1 = gen_best_f1
            self.global_best_prec = gen_best_prec
        elif gen_best_f1 == self.global_best_f1 and gen_best_prec > self.global_best_prec:
            self.global_best_prec = gen_best_prec

        return res

    def run_atomic_scan(self):
        """Repopulates the weakest population members using high-vitality genes.

        This method computes a vitality score for each gene based on its
        historical importance and usage frequency, selects the top-N most
        vital genes, and reinitializes the bottom fraction of the population
        using random combinations drawn from this high-quality gene pool.

        Args:
            top_n_vitality (int, optional): Number of top-ranked genes (by
                vitality score) eligible for reseeding the population.
                Defaults to 40.

        Side Effects:
            - Modifies gene selections for the weakest population members.
            - Reinitializes corresponding network weights and biases.
        """

        # Compute gene vitality:
        # encourages high-impact genes while penalizing overused ones
        vitality = (self.gene_scores + 0.1) / (self.gene_usage + 1.0)

        # Better poolsize handling
        pool_size = max(int(self.gene_count * 1.5), 40)
        
        # Ensure we don't try to grab more indicators than actually exist in the lake
        pool_size = min(pool_size, len(self.feature_names))

        # Select indices of top-N most vital genes
        pool = torch.argsort(vitality, descending=True)[:pool_size]

        assert len(pool) == len(torch.unique(pool)), "Vitality pool contains duplicates!"

        # Define the cutoff for weakest population members (bottom 20%)
        start_idx = int(self.pop_size * 0.8)

        # Reseed weakest individuals with fresh gene combinations
        for i in range(start_idx, self.pop_size):

            # Randomly sample genes from the vitality pool without replacement
            self.population[i] = pool[
                torch.randperm(len(pool), generator=self.torch_generator)[:self.gene_count]
            ].to(self.device)

            # Reinitialize first-layer weights (He initialization)
            self.pop_W1[i] = (
                torch.randn(self.gene_count, self.hidden_dim, device=self.device, generator=self.cuda_generator)
                * np.sqrt(2.0 / self.gene_count)
            )

            # Reinitialize second-layer weights (He initialization)
            self.pop_W2[i] = (
                torch.randn(self.hidden_dim, 1, device=self.device, generator=self.cuda_generator)
                * np.sqrt(2.0 / self.hidden_dim)
            )

            # Reset second-layer bias to a negative baseline
            self.pop_B2[i] = -2.0

    def evolve(self, fitness_scores):
        """Evolves the population using elitism, crossover, and mutation.

        This method ranks the population by primary fitness score, preserves
        the best-performing individual by F1 score (champion), applies
        elitism, and generates a new population through genetic crossover
        and mutation. Finally, it performs an atomic gene scan to refresh
        weak individuals using high-vitality genes.

        Args:
            fitness_scores: Placeholder for external fitness inputs.
                Currently unused; evolution is driven by internal metrics
                (`latest_f1` and `latest_score`).

        Side Effects:
            - Reorders and replaces population members.
            - Mutates gene selections, network weights, and thresholds.
            - Updates global best F1 score.
            - Triggers an atomic scan to inject high-vitality genes.
        """

        # Retrieve latest generation metrics
        f1_scores = self.latest_f1.to(self.device).flatten()
        primary_scores = self.latest_score.to(self.device).flatten()
        
        # Identify best individual by F1 score (generation champion)
        gen_best_f1_val, gen_best_f1_idx = torch.max(f1_scores, dim=0)
        
        # Store champion's complete state BEFORE any reordering
        champ_pop = self.population[gen_best_f1_idx].clone()
        champ_w1 = self.pop_W1[gen_best_f1_idx].clone()
        champ_b1 = self.pop_B1[gen_best_f1_idx].clone()
        champ_w2 = self.pop_W2[gen_best_f1_idx].clone()
        champ_b2 = self.pop_B2[gen_best_f1_idx].clone()
        champ_thresh = self.thresholds[gen_best_f1_idx].clone()
        champ_f1 = gen_best_f1_val.clone()
        
        # Rank population by primary fitness score (descending)
        idx = torch.argsort(primary_scores, descending=True)
        
        # Reorder population and parameters by fitness ranking
        self.population = self.population[idx]
        self.thresholds = self.thresholds[idx]
        self.pop_W1, self.pop_B1 = self.pop_W1[idx], self.pop_B1[idx]
        self.pop_W2, self.pop_B2 = self.pop_W2[idx], self.pop_B2[idx]
        f1_scores = f1_scores[idx]  # Also reorder F1 scores for consistency
        
        # FIXED: Remove global best update from here - moved to run_generation
        
        # Number of elite individuals preserved unchanged
        keep = max(2, self.pop_size // 10)
        
        # Initialize new population containers
        new_pop = self.population.clone()
        new_w1, new_b1 = self.pop_W1.clone(), self.pop_B1.clone()
        new_w2, new_b2 = self.pop_W2.clone(), self.pop_B2.clone()
        new_thresh = self.thresholds.clone()
        
        # FIXED: Force champion into top 2 positions using stored state (not gene comparison)
        # Always put champion in slot 1 (keep slot 0 as best by score)
        new_pop[1] = champ_pop
        new_w1[1], new_b1[1] = champ_w1, champ_b1
        new_w2[1], new_b2[1] = champ_w2, champ_b2
        new_thresh[1] = champ_thresh
        
        if self.verbose:
            print(f"💎 [Singularity]: Quantum Lock: Champion (F1={champ_f1:.4f}) pinned to Elite Slot 1")
        
        # Standard deviation for weight mutation noise
        mutation_std = self.weight_mutation_rate
        
        # Generate offspring for non-elite population members
        for i in range(keep, self.pop_size):
            
            # Randomly select two elite parents
            p1, p2 = torch.randint(0, keep, (2,), generator=self.torch_generator)
            
            # Crossover with 70% probability
            if torch.rand(1, generator=self.torch_generator).item() < 0.7:
                # One-point crossover on gene indices
                cut = torch.randint(0, self.gene_count, (1,), generator=self.torch_generator).item()
                
                # OPTIMIZED: Ensure unique genes after crossover
                # Concatenate genes from both parents
                child_genes = torch.cat([
                    self.population[p1, :cut],
                    self.population[p2, cut:]
                ])
                
                # Fast uniqueness check using broadcasting
                unique_mask = torch.zeros(len(self.feature_names), dtype=torch.bool, device=self.device)
                unique_mask[child_genes] = True
                unique_count = unique_mask.sum().item()
                
                if unique_count < self.gene_count:
                    # We have duplicates - need to replace them
                    
                    # Get available genes (not in child_genes)
                    available_mask = ~unique_mask
                    available = torch.where(available_mask)[0].cpu().numpy()
                    
                    # Get unique genes (remove duplicates)
                    fixed_genes = child_genes.unique().tolist()
                    
                    # Fill remaining slots with random available genes
                    needed = self.gene_count - len(fixed_genes)
                    if needed > 0 and len(available) >= needed:
                        # Randomly sample without replacement
                        new_genes = np.random.choice(available, needed, replace=False)
                        fixed_genes.extend(new_genes.tolist())
                        # Convert back to tensor
                        new_pop[i] = torch.tensor(fixed_genes, device=self.device)
                    else:
                        new_pop[i] = child_genes  # Keep original if no fix needed
                else:
                    new_pop[i] = child_genes
                
                # Blend weights and thresholds using convex combination
                alpha = torch.rand(1, device=self.device, generator=self.cuda_generator) * 0.2 + 0.4
                new_w1[i] = alpha * self.pop_W1[p1] + (1 - alpha) * self.pop_W1[p2]
                new_w2[i] = alpha * self.pop_W2[p1] + (1 - alpha) * self.pop_W2[p2]
                new_thresh[i] = (
                    alpha * self.thresholds[p1]
                    + (1 - alpha) * self.thresholds[p2]
                )
            
            # Mutation-only path (30% probability)
            else:
                # Clone parent genes
                child_genes = self.population[p1].clone()
                
                # OPTIMIZED: Apply gene-level mutation with uniqueness check
                # 30% chance to mutate genes (in addition to weight mutation)
                if torch.rand(1, generator=self.torch_generator).item() < 0.3:
                    # Randomly select how many genes to mutate (1-3)
                    n_mutations = torch.randint(1, min(4, self.gene_count), (1,), generator=self.torch_generator).item()
                    
                    # Fast uniqueness check for current genes
                    current_unique_mask = torch.zeros(len(self.feature_names), dtype=torch.bool, device=self.device)
                    current_unique_mask[child_genes] = True
                    
                    # Get available genes
                    available_mask = ~current_unique_mask
                    available = torch.where(available_mask)[0].cpu().numpy()
                    
                    if len(available) >= n_mutations:
                        # Randomly choose positions to mutate
                        mutate_positions = torch.randperm(self.gene_count, generator=self.torch_generator)[:n_mutations]
                        
                        # Sample new unique genes
                        new_genes = np.random.choice(available, n_mutations, replace=False)
                        
                        # Apply mutations
                        for pos, new_gene in zip(mutate_positions, new_genes):
                            child_genes[pos] = new_gene
                
                new_pop[i] = child_genes
                
                # Apply Gaussian noise to weights
                new_w1[i] = (
                    self.pop_W1[p1]
                    + torch.randn_like(self.pop_W1[p1]) * mutation_std
                )
                new_w2[i] = (
                    self.pop_W2[p1]
                    + torch.randn_like(self.pop_W2[p1]) * mutation_std
                )
                
                # Slightly mutate decision threshold
                new_thresh[i] = (
                    self.thresholds[p1]
                    + torch.randn(1, device=self.device, generator=self.cuda_generator).squeeze() * 0.01
                )
        
        # OPTIMIZED: Final uniqueness verification across entire population (vectorized)
        # Create boolean mask for all genes at once
        all_genes = new_pop  # Shape: (pop_size, gene_count)
        pop_size, gene_count = all_genes.shape
        
        # Sort each row to detect duplicates
        sorted_genes, _ = torch.sort(all_genes, dim=1)
        # Duplicates exist if consecutive elements are equal
        dup_mask = (sorted_genes[:, 1:] == sorted_genes[:, :-1]).any(dim=1)
        
        # Get indices of individuals with duplicates
        dup_indices = torch.where(dup_mask)[0].cpu().numpy()
        
        for i in dup_indices:
            # Fix duplicates for this individual
            genes = new_pop[i]
            unique_genes = genes.unique()
            fixed_genes = unique_genes.tolist()
            
            # Vectorized available gene calculation
            used_mask = torch.zeros(len(self.feature_names), dtype=torch.bool, device=self.device)
            used_mask[fixed_genes] = True
            available = torch.where(~used_mask)[0].cpu().numpy()
            
            needed = self.gene_count - len(fixed_genes)
            if needed > 0 and len(available) >= needed:
                new_genes = np.random.choice(available, needed, replace=False)
                fixed_genes.extend(new_genes.tolist())
                new_pop[i] = torch.tensor(fixed_genes, device=self.device)
                if self.verbose:
                    print(f"    🔧 Post-processing fix for individual {i}")
        
        # FIXED: Final sanity check - ensure champion still exists (using stored state, not gene comparison)
        champ_exists = (new_pop == champ_pop.unsqueeze(0)).all(dim=1).any()
        if not champ_exists:
            # Champion was lost during crossover/mutation - restore it
            if self.verbose:
                print(f"  ⚠️ [Evolution]: Champion lost! Restoring to position 1")
            new_pop[1] = champ_pop
            new_w1[1], new_b1[1] = champ_w1, champ_b1
            new_w2[1], new_b2[1] = champ_w2, champ_b2
            new_thresh[1] = champ_thresh
        
        # Commit evolved population
        self.population = new_pop
        self.pop_W1, self.pop_B1 = new_w1, new_b1
        self.pop_W2, self.pop_B2 = new_w2, new_b2
        
        # Clamp thresholds to valid probability range
        self.thresholds = torch.clamp(new_thresh, 0.10, 0.85)
        
        # FIXED: Atomic scan moved to separate phase (call it from training loop, not here)
        # self.run_atomic_scan()

    def emit(self, features: pd.DataFrame) -> np.ndarray:
        """Generates binary signals from input features using the best individual.

        This method performs inference using the top-ranked population member
        (index 0), applies its learned feature selection, neural network
        weights, and decision threshold, and returns binary predictions
        for each input row.

        Args:
            features (pd.DataFrame): Input feature matrix with shape
                (T, F), where T is the number of time steps or samples and
                F is the total number of available features.

        Returns:
            np.ndarray: Flattened binary array of shape (T,) indicating
            emitted signals (1 = signal, 0 = no signal).
        """

        # Handle empty input defensively
        if len(features) == 0:
            return np.array([])

        # Disable gradient tracking for inference
        with torch.no_grad():

            # Convert input features to float32 tensor on target device
            x = torch.tensor(
                features.values.astype(np.float32),
                device=self.device
            )

            # Select genes used by the best population member
            # Shape: (1, T, G)
            x_sel = x[:, self.population[0]].unsqueeze(0)

            # Forward pass through the champion network
            logits = self._forward(
                x_sel,
                self.pop_W1[0:1],
                self.pop_B1[0:1],
                self.pop_W2[0:1],
                self.pop_B2[0:1],
            )

            # Apply sigmoid and threshold to produce binary output
            return (
                torch.sigmoid(logits) > self.thresholds[0]
            ).cpu().numpy().flatten()

    def save_state(self, universe, filename: str, winner_idx: Optional[int] = None):
        """Serializes and saves the best-performing model state.

        This method identifies a winning population member (either explicitly
        provided or inferred from the latest F1 scores), extracts its learned
        parameters and selected feature subset, and persists the model state
        via the provided universe interface.

        Args:
            universe: Object responsible for persistence. Must implement
                an `eject(filename, state, is_model=True)` method.
                filename (str): Destination path or identifier for the saved state.
                winner_idx (Optional[int]): Index of the population member to save.
                    If None, the best individual by latest F1 score is selected.

        Side Effects:
                - Writes model state to disk or external storage.
                - Emits a verbose log message when enabled.
                - Safely extracts and bundles Redshift global scaling physics.
        """
        # Determine current best F1 and precision
        current_best_f1 = torch.max(self.latest_f1).item() if self.latest_f1 is not None else -1.0
        current_best_idx = torch.argmax(self.latest_f1).item() if self.latest_f1 is not None else 0
        current_best_prec = self.latest_precision[current_best_idx].item() if self.latest_precision is not None else 0.0
        
        # PERSISTENCE GATE: Only save if F1 has improved OR F1 equal with better precision
        should_save = False
        reason = ""
        
        if current_best_f1 > self.global_best_f1:
            should_save = True
            reason = f"new F1 record ({current_best_f1:.4f} > {self.global_best_f1:.4f})"
            # Update global best precision when F1 improves
            self.global_best_prec = current_best_prec
        elif current_best_f1 == self.global_best_f1 and self.global_best_f1 > 0:
            if current_best_prec > self.global_best_prec:
                should_save = True
                reason = f"same F1 ({current_best_f1:.4f}) but better precision ({current_best_prec:.4f} > {self.global_best_prec:.4f})"
                self.global_best_prec = current_best_prec
            else:
                reason = f"same F1 ({current_best_f1:.4f}) but precision not improved"
        else:
            reason = f"{current_best_f1:.4f} is not better than {self.global_best_f1:.4f}"
        
        if not should_save:
            if self.verbose:
                print(f"🛑 [Singularity]: Save aborted. {reason}")
            return
        
        # FIXED: Determine which population member to persist - ALWAYS the best one
        if winner_idx is None:
            if self.latest_f1 is not None:
                # Select best individual based on latest F1 performance (not just index 0)
                winner_idx = torch.argmax(self.latest_f1).item()
                if self.verbose:
                    print(f"  📍 [Singularity]: Saving best model at index {winner_idx} with F1={current_best_f1:.4f}, Precision={current_best_prec:.4f}")
            else:
                # Fallback to the first population member
                winner_idx = 0
                if self.verbose:
                    print(f"  ⚠️ [Singularity]: No F1 scores, saving index 0")
        
        # Extract gene indices for the winning individual
        winner_genes = self.population[winner_idx].cpu().tolist()
        
        # Map gene indices back to original feature names
        atomic_feature_map = [self.feature_names[i] for i in winner_genes]
        
        # Assemble serializable model state
        state = {
            # Population is remapped to a compact [0..N-1] index space
            'population': torch.arange(len(atomic_feature_map)),
            'threshold': self.thresholds[winner_idx].cpu(),
            'W1': self.pop_W1[winner_idx].cpu(),
            'B1': self.pop_B1[winner_idx].cpu(),
            'W2': self.pop_W2[winner_idx].cpu(),
            'B2': self.pop_B2[winner_idx].cpu(),
            'feature_names': atomic_feature_map,
            'config': self.config,
            'f1': current_best_f1,
            'precision': current_best_prec  # NEW: Save precision too
        }
        
        # --- FACTORY SPEC FIX: Inject Scaling Physics ---
        # We need the global Means and Stds specifically for the winner_genes
        if hasattr(universe, '_normalizers') and 'Redshift' in universe._normalizers:
            redshift = universe._normalizers['Redshift']
            if hasattr(redshift, 'means') and hasattr(redshift, 'stds'):
                try:
                    # PyTorch tensors have a built-in method called .values(), so we must check is_tensor first
                    if torch.is_tensor(redshift.means):
                        state['means'] = redshift.means.detach()[winner_genes].float().cpu()
                        state['stds'] = redshift.stds.detach()[winner_genes].float().cpu()
                    else:
                        # Fallback for numpy arrays or lists
                        state['means'] = torch.as_tensor(redshift.means)[winner_genes].float().cpu()
                        state['stds'] = torch.as_tensor(redshift.stds)[winner_genes].float().cpu()
                except Exception as e:
                    if self.verbose:
                        print(f"⚠️ [Singularity]: Failed to extract Redshift physics: {e}")
        
        # Delegate persistence to universe
        universe.eject(filename, state, is_model=True)
        
        # Optional logging
        if self.verbose:
            print(
                f"🥇 [Singularity]: Atomic Winner Ejected. "
                f"Features: {len(atomic_feature_map)} | F1: {current_best_f1:.4f} | Precision: {current_best_prec:.4f}"
            )

    def state_dict(self):
        """Returns a lightweight snapshot of the evolutionary state.

        This method exports the core evolutionary metadata required to
        resume or analyze the genetic search process, excluding large
        neural network weight tensors.

        Returns:
            dict[str, Any]: Dictionary containing:
                - 'population': Current gene indices per individual.
                - 'gene_scores': Accumulated gene importance scores.
                - 'gene_usage': Gene selection frequency statistics.
                - 'config': Configuration object used for initialization.
                - 'feature_names': List of original feature names.

        Notes:
            - All tensors are detached and moved to CPU to ensure safe
            serialization.
            - Model weights (W1, W2, etc.) are intentionally excluded.
        """

        return {
            # Gene index matrix for entire population
            'population': self.population.detach().cpu(),

            # Running importance scores for each gene
            'gene_scores': self.gene_scores.detach().cpu(),

            # Gene usage frequency tracker
            'gene_usage': self.gene_usage.detach().cpu(),

            # Configuration parameters for reproducibility
            'config': self.config,

            # Original feature name mapping
            'feature_names': self.feature_names,
        }