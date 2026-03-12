"""
===============================================================================
File:        rpulsar2.py
Author:      JP Ueberbach
Created:     2026-03-12
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
import torch.optim as optim
import numpy as np
import pandas as pd
from typing import Optional, Dict, Any

from ml.space.space import Singularity
from ml.space.lenses.factory import LensFactory
from ml.space.singularities.cores.rpulsar_core2 import RPulsarCore2

class RPulsarSingularity2(Singularity):
    """
    Orchestrator for the Recurrent Pulsar Evolutionary Core.
    
    Manages the high-level execution of the evolutionary algorithm, including
    data ingestion, batched GPU execution, gradient optimization, temporal 
    windowing, and state persistence.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initializes the RPulsarSingularity orchestrator.

        Args:
            config (Dict[str, Any]): Configuration dictionary containing hyperparameters
                for orchestration, thresholding, penalties, and network sizes.
        """
        super().__init__(device=config.get('device'))
        self.config = config
        
        # Orchestration and constraint hyperparameters
        self.decay_factor = float(self.config.get('decay_factor', 0.9))
        self.chunk_size = int(self.config.get("gpu_chunk", 256))
        self.min_sigs = int(self.config.get("min_signals", 3))
        self.target_density = float(self.config.get("target_density", 0.01))
        self.precision_exp = float(self.config.get("precision_exp", 2.5))
        self.penalty_coeff = float(self.config.get("penalty_coeff", 1.0))
        self.thresh_steps = int(self.config.get("thresh_steps", 31))
        self.oos_boundary = float(self.config.get("oos_boundary", 0.75))
        self.epochs = int(self.config.get("epochs", 25))
        self.verbose = bool(self.config.get("verbose", True))

        # Instantiate the underlying mathematical tensor core
        self.core = RPulsarCore2(config, self.device, self.config.get('seed', 42))

        # Initialize the loss function (lens) mapping predictions to reality
        self.lens = LensFactory.manifest(
            self.config.get("lens", {}).get("type", "Gravitational"), 
            self.config.get("lens", {})
        )
 
        # Data tensors
        self.lake = None
        self.y_all = None
        
        # Global state tracking across generations
        self.global_best_f1 = -1.0
        self.global_best_prec = 0.0 
        self.latest_f1 = None
        self.latest_score = None
        self.latest_precision = None 

    def compress(self, universe: Any) -> None:
        """
        Ingests the global dataset and prepares the tensor environment.

        Extracts features and targets from the provided universe, converts them
        into GPU-resident PyTorch tensors, and initializes the population matrices.

        Args:
            universe (Any): The data container/environment providing the 'bigbang' 
                method to extract raw DataFrames and targets.
        """
        self.universe = universe
        feature_df, target_series = universe.bigbang()
        num_indicators = len(feature_df.columns)
        
        # Convert raw DataFrame values into high-speed float32 NumPy arrays, filtering NaNs
        vals = np.nan_to_num(feature_df.values.astype(np.float32))
        self.lake = torch.tensor(vals, device=self.device)
        
        # Reshape targets to [Batch(1), Time_Steps, Target_Dim(1)] for broadcasting
        self.y_all = torch.tensor(
            target_series.values.astype(np.float32),
            device=self.device
        ).view(1, -1, 1)

        # Delegate the actual matrix initializations to the physical Core
        self.core.init_population(num_indicators, list(feature_df.columns))

        # Establish proxy properties required by higher-level orchestrators (e.g., Flight)
        self.population = self.core.population
        self.gene_scores = self.core.gene_scores
        self.gene_usage = self.core.gene_usage
        self.feature_names = self.core.feature_names

    def run_generation(self, config: Dict[str, Any]) -> Dict[str, torch.Tensor]:
        """
        Executes a single generational step evaluating the entire population.

        This method processes the population in GPU-sized chunks. It applies
        spatio-temporal windowing to the data, performs gradient-based updates
        on the neural weights, evaluates out-of-sample performance across multiple
        thresholds, and computes vitality scores for the genes.

        Args:
            config (Dict[str, Any]): Generation-specific runtime configuration.

        Returns:
            Dict[str, torch.Tensor]: A dictionary containing metric tensors 
                (f1, precision, recall, score, etc.) for every individual in the population.
        """
        metrics = {"f1": [], "sigs": [], "density": [], "precision": [], "recall": [], "score": [], "signal_map": []}
        
        # Define the chronological split between training and out-of-sample validation
        train_end = int(len(self.lake) * self.oos_boundary)

        # Decay historical gene vitality to favor currently performing genes
        self.core.gene_scores *= self.decay_factor
        self.core.gene_usage *= self.decay_factor

        # Process the vast population in manageable VRAM chunks
        for i in range(0, self.core.pop_size, self.chunk_size):
            end_i = min(i + self.chunk_size, self.core.pop_size)
            curr_chunk = end_i - i

            indices = self.core.population[i:end_i]
            lookback = self.core.lookback
            
            # =========================================================================
            # RECURRENT SPATIO-TEMPORAL WINDOWING (TRAIN)
            # =========================================================================
            # Extract raw historical data exclusively for the genes active in this chunk
            raw_x_train = self.lake[:train_end, indices] 
            
            # PyTorch Unfold creates overlapping sliding windows representing the timeline.
            # This allows the feedforward network to perceive velocity and acceleration.
            # Resulting shape: (Num_Windows, Chunk_Size, Gene_Count, Lookback)
            windows_x_train = raw_x_train.unfold(dimension=0, size=lookback, step=1)
            
            # Permute dimensions to align with expected forward pass architecture
            # Target shape: (Chunk_Size, Num_Windows, Gene_Count, Lookback)
            windows_x_train = windows_x_train.permute(1, 0, 2, 3) 
            
            # Flatten the spatial (Gene) and temporal (Lookback) dimensions into a single
            # vector. The network will evaluate this entire block simultaneously.
            num_windows = windows_x_train.size(1)
            x_train = windows_x_train.reshape(curr_chunk, num_windows, -1) 
            
            # Because the first 'lookback' frames are consumed to construct the first window,
            # the target labels must be shifted forward to maintain exact temporal alignment.
            y_train = self.y_all[:, (lookback - 1):train_end, :].expand(curr_chunk, -1, -1)

            # Detach and track gradients for internal backpropagation
            w1 = self.core.pop_W1[i:end_i].detach().requires_grad_(True)
            b1 = self.core.pop_B1[i:end_i].detach().requires_grad_(True)
            w2 = self.core.pop_W2[i:end_i].detach().requires_grad_(True)
            b2 = self.core.pop_B2[i:end_i].detach().requires_grad_(True)

            optimizer = optim.Adam([w1, b1, w2, b2], lr=0.0005)

            # Intra-generational gradient descent loop
            for _ in range(self.epochs):
                optimizer.zero_grad()
                logits = self.core.forward(x_train, w1, b1, w2, b2)
                main_loss = self.lens.forward(logits, y_train)
                
                # Kullback-Leibler inspired density penalty to prevent signal spam
                target_mean = torch.tensor(self.target_density, device=self.device)
                current_mean = torch.sigmoid(logits).mean()
                
                kl_penalty = self.penalty_coeff * (
                    current_mean * torch.log(current_mean / target_mean + 1e-8) +
                    (1 - current_mean) * torch.log((1 - current_mean) / (1 - target_mean + 1e-8) + 1e-8)
                )
                
                # L1 penalty on the final bias to encourage sparse activations
                b2_penalty = 0.001 * torch.abs(b2).mean()
                
                loss = main_loss + kl_penalty + b2_penalty
                loss.backward()

                # Protect global elites (indices 0 and 1) from gradient degradation.
                # Their weights must remain pure and only change via genetic mutation.
                chunk_indices_global = torch.arange(i, end_i, device=self.device)
                global_elites = torch.tensor([0, 1], device=self.device)
                elite_mask = torch.isin(chunk_indices_global, global_elites)
                
                if elite_mask.any():
                    w1.grad[elite_mask] = 0
                    b1.grad[elite_mask] = 0
                    w2.grad[elite_mask] = 0
                    b2.grad[elite_mask] = 0

                torch.nn.utils.clip_grad_norm_([w1, b1, w2, b2], max_norm=1.0)
                optimizer.step()

            # Evaluation and metric calculation must not track gradients
            with torch.no_grad():
                # Write back the optimized weights to the Core state
                self.core.pop_W1[i:end_i].copy_(w1)
                self.core.pop_B1[i:end_i].copy_(b1)
                self.core.pop_W2[i:end_i].copy_(w2)
                self.core.pop_B2[i:end_i].copy_(b2)

                # =========================================================================
                # RECURRENT SPATIO-TEMPORAL WINDOWING (OUT OF SAMPLE)
                # =========================================================================
                raw_x_oos = self.lake[train_end:, indices]
                windows_x_oos = raw_x_oos.unfold(dimension=0, size=lookback, step=1)
                windows_x_oos = windows_x_oos.permute(1, 0, 2, 3)
                num_oos_windows = windows_x_oos.size(1)
                
                x_oos = windows_x_oos.reshape(curr_chunk, num_oos_windows, -1)
                y_oos = self.y_all[:, train_end + (lookback - 1):, :].expand(curr_chunk, -1, -1)                
                
                # Execute inference on unseen data
                oos_probs = torch.sigmoid(self.core.forward(x_oos, w1, b1, w2, b2))

                oos_target_count = y_oos[0].sum().item()
                best_score = torch.full((curr_chunk,), -1e9, device=self.device)
                best_f1 = torch.zeros(curr_chunk, device=self.device)
                best_thresh = torch.full((curr_chunk,), 0.40, device=self.device)
                best_sigs = torch.zeros(curr_chunk, device=self.device)
                best_prec = torch.zeros(curr_chunk, device=self.device)
                best_rec = torch.zeros(curr_chunk, device=self.device)
                best_preds = torch.zeros_like(oos_probs, device=self.device)

                # Grid search optimal signal thresholds
                for t in torch.linspace(0.15, 0.85, self.thresh_steps):
                    preds = (oos_probs > t).float()
                    sig_count = preds.sum(dim=1).view(-1)
                    density = preds.mean(dim=1).view(-1)

                    tp = (preds * y_oos).sum(dim=1).view(-1)
                    fp = (preds * (1 - y_oos)).sum(dim=1).view(-1)
                    fn = ((1 - preds) * y_oos).sum(dim=1).view(-1)

                    prec = tp / (tp + fp + 1e-8)
                    rec = tp / (tp + fn + 1e-8)
                    f1 = 2 * prec * rec / (prec + rec + 1e-8)

                    # Custom scoring function prioritizing F1 bounded by exponential precision
                    score = f1 * torch.clamp(torch.pow(prec, self.precision_exp), max=5.0)

                    # Penalize models diverging significantly from the target signal density
                    min_density = self.min_sigs / oos_probs.shape[1]
                    dev_high = torch.relu(density - self.target_density * 1.5) * 15.0
                    dev_low = torch.relu(min_density * 0.8 - density) * 6.0
                    score = score - (dev_high + dev_low)

                    # Eradicate non-viable strategies (too few signals or abysmal precision)
                    score = torch.where((sig_count >= self.min_sigs) & (prec > 0.02), score, torch.full_like(score, -1e9))

                    mask = score > best_score
                    best_score[mask] = score[mask]
                    best_f1[mask] = f1[mask]
                    best_thresh[mask] = t
                    best_sigs[mask] = sig_count[mask]
                    best_prec[mask] = prec[mask]
                    best_rec[mask] = rec[mask]
                    best_preds[mask] = preds[mask]


                if self.verbose:
                    self.print(
                        "PULSAR_CHUNK_LOG", 
                        chunk=i//self.chunk_size, 
                        max_p=oos_probs.max().item(), 
                        targets=oos_target_count, 
                        fired=best_sigs.max().item(), 
                        f1=best_f1.max().item()
                    )

                # Persist optimal thresholds found during grid search
                self.core.thresholds[i:end_i] = best_thresh

                # Calculate relative impact of specific genes based on weight magnitude
                gene_imp = torch.bmm(w1.abs(), w2.abs()).squeeze(-1)
                imp_norm = gene_imp / (gene_imp.sum(dim=1, keepdim=True) + 1e-7)
                
                # Normalize performance scores to assign proportional vitality to active genes
                score_range = best_score.max() - best_score.min()
                norm_scores = torch.where(
                    score_range > 1e-8,
                    (best_score - best_score.min()) / score_range,
                    torch.full_like(best_score, 0.5)  # Default neutral contribution if uniform
                )

                # Accumulate gene vitality for future reproduction and selection phases
                self.core.gene_scores.scatter_add_(0, indices.view(-1), (imp_norm * norm_scores.view(-1, 1)).reshape(-1))
                self.core.gene_usage.scatter_add_(0, indices.view(-1), torch.ones(indices.numel(), device=self.device))

                # Aggregate chunk metrics
                metrics["f1"].append(best_f1.detach().cpu())
                metrics["sigs"].append(best_sigs.detach().cpu())
                metrics["density"].append((best_sigs / oos_probs.shape[1]).detach().cpu())
                metrics["precision"].append(best_prec.detach().cpu())
                metrics["recall"].append(best_rec.detach().cpu())
                metrics["score"].append(best_score.detach().cpu())
                metrics["signal_map"].append(best_preds.squeeze(-1).detach().cpu())

        # Compile final generation metrics
        res = {k: torch.cat(v) for k, v in metrics.items()}
        self.latest_f1 = res["f1"].clone()
        self.latest_score = res["score"].clone()
        self.latest_precision = res["precision"].clone()

        # Assess if the current generation yielded a historic champion
        self._pending_save = False
        if self.latest_f1 is not None:
            gen_best_idx = torch.argmax(self.latest_f1).item()
            gen_best_f1 = self.latest_f1[gen_best_idx].item()
            gen_best_prec = self.latest_precision[gen_best_idx].item()

            should_save = False
            reason = ""

            # Check primary F1 improvement or tie-breaking precision improvement
            if gen_best_f1 > self.global_best_f1 + 1e-6:
                should_save = True
                reason = f"new F1 record ({gen_best_f1:.4f} > {self.global_best_f1:.4f})"
            elif abs(gen_best_f1 - self.global_best_f1) < 1e-6 and gen_best_f1 > 0:
                if gen_best_prec > self.global_best_prec + 1e-6:
                    should_save = True
                    reason = f"same F1 but better prec ({gen_best_prec:.4f} > {self.global_best_prec:.4f})"

            if should_save:
                self._pending_save = True
                self._pending_save_idx = gen_best_idx
                self._pending_save_f1 = gen_best_f1
                self._pending_save_prec = gen_best_prec
                self.global_best_f1 = gen_best_f1 
                self.global_best_prec = gen_best_prec
                if self.verbose:
                    self.print("PULSAR_NEW_RECORD", reason=reason)

        return res

    def run_atomic_scan(self) -> None:
        """
        Invokes the vitality evaluation within the Core.
        
        This process eliminates weak or dead-weight feature combinations 
        and repopulates the weakest individuals with historically successful genes.
        """
        self.core.run_atomic_scan()

    def evolve(self, metrics: Dict[str, Any]) -> None:
        """
        Triggers the biological reproduction cycle.
        
        Delegates the elitism, crossover, and genetic mutation mechanisms to 
        the Core, ensuring structural integrity of the temporal windows during 
        weight manipulation.

        Args:
            metrics (Dict[str, Any]): Dictionary containing fitness scores used 
                to guide selection probabilities.
        """
        self.core.evolve(self.latest_f1, self.latest_score)
        # Re-synchronize proxy state for higher-order orchestrators
        self.population = self.core.population

    def emit(self, features: pd.DataFrame) -> np.ndarray:
        """
        Performs live inference using the reigning global champion.

        Args:
            features (pd.DataFrame): The live incoming feature matrix.

        Returns:
            np.ndarray: A boolean array representing the binary trading signals.
        """
        return self.core.emit(features)

    def save_state(self, universe: Any, filename: str, winner_idx: Optional[int] = None) -> None:
        """
        Serializes the highest-performing network and its genome to disk.
        """
        if not hasattr(self, '_pending_save') or not self._pending_save:
            if self.verbose:
                self.print("PULSAR_SAVE_ABORT", reason="no pending save queued")
            return

        current_best_f1  = self._pending_save_f1
        current_best_prec = self._pending_save_prec
        winner_idx       = self._pending_save_idx if winner_idx is None else winner_idx
        self._pending_save = False

        if self.verbose:
            self.print(
                "PULSAR_SAVE_PENDING",
                f1=current_best_f1,
                prec=current_best_prec,
                winner_idx=winner_idx
            )

        # =====================================================================
        # ROUGH PATH FIX: Strict Sequence Preservation
        # =====================================================================
        winner_genes = self.core.population[winner_idx].cpu().tolist()
        atomic_feature_map = [self.core.feature_names[i] for i in winner_genes]

        state = {
            'population': torch.arange(len(atomic_feature_map)),
            'threshold': self.core.thresholds[winner_idx].cpu(),
            'W1': self.core.pop_W1[winner_idx].cpu(),
            'B1': self.core.pop_B1[winner_idx].cpu(),
            'W2': self.core.pop_W2[winner_idx].cpu(),
            'B2': self.core.pop_B2[winner_idx].cpu(),
            'feature_names': atomic_feature_map,
            'config': self.config,
            'f1': current_best_f1,
            'precision': current_best_prec
        }

        if hasattr(universe, '_normalizers') and 'Redshift' in universe._normalizers:
            redshift = universe._normalizers['Redshift']
            if hasattr(redshift, 'means') and hasattr(redshift, 'stds'):
                try:
                    if torch.is_tensor(redshift.means):
                        state['means'] = redshift.means.detach()[winner_genes].float().cpu()
                        state['stds'] = redshift.stds.detach()[winner_genes].float().cpu()
                    else:
                        state['means'] = torch.as_tensor(redshift.means)[winner_genes].float().cpu()
                        state['stds'] = torch.as_tensor(redshift.stds)[winner_genes].float().cpu()
                except Exception as e:
                    if self.verbose:
                        self.print("PULSAR_PHYSICS_FAIL", error=str(e))

        universe.eject(filename, state, is_model=True)

        if self.verbose:
            self.print(
                "PULSAR_WINNER_EJECT",
                features=len(atomic_feature_map),
                f1=current_best_f1,
                prec=current_best_prec
            )

    def state_dict(self) -> Dict[str, Any]:
        """
        Exposes the entire evolutionary status for resumption capabilities.

        Returns:
            Dict[str, Any]: Snapshot of the current genetic population and scoring metrics.
        """
        return {
            'population': self.core.population.detach().cpu(),
            'gene_scores': self.core.gene_scores.detach().cpu(),
            'gene_usage': self.core.gene_usage.detach().cpu(),
            'config': self.config,
            'feature_names': self.core.feature_names,
        }