"""
===============================================================================
 File:        pulsar2.py
 Author:      JP Ueberbach
 Created:     2026-02-27

 Description:
     The high-level orchestrator for the Pulsar architecture.
     Manages chunked execution, threshold optimization, metric calculation,
     and model persistence. Defers heavy tensor operations to PulsarCore2.
===============================================================================
"""
import torch
import torch.optim as optim
import numpy as np
import pandas as pd
from typing import Optional

from ml.space.space import Singularity
from ml.space.lenses.factory import LensFactory
from ml.space.singularities.cores.pulsar_core import PulsarCore

class PulsarSingularity(Singularity):
    """Orchestrator for the Pulsar Evolutionary Core."""

    def __init__(self, config):
        super().__init__(device=config.get('device'))
        self.config = config
        
        # Setup Orchestration Constraints
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

        # Initialize the Physical Core
        self.core = PulsarCore(config, self.device, self.config.get('seed', 42))

        self.lens = LensFactory.manifest(
            self.config.get("lens",{}).get("type","Gravitational"), 
            self.config.get("lens", {})
        )
 
        self.lake = None
        self.y_all = None
        
        # State Tracking
        self.global_best_f1 = -1.0
        self.global_best_prec = 0.0 
        self.latest_f1 = None
        self.latest_score = None
        self.latest_precision = None 

    def compress(self, universe):
        self.universe = universe
        feature_df, target_series = universe.bigbang()
        num_indicators = len(feature_df.columns)
        
        vals = np.nan_to_num(feature_df.values.astype(np.float32))
        self.lake = torch.tensor(vals, device=self.device)
        self.y_all = torch.tensor(
            target_series.values.astype(np.float32),
            device=self.device
        ).view(1, -1, 1)

        # Delegate Tensor Matrix Init
        self.core.init_population(num_indicators, list(feature_df.columns))

        # Proxy properties required by MilleniumFalcon Flight
        self.population = self.core.population
        self.gene_scores = self.core.gene_scores
        self.gene_usage = self.core.gene_usage
        self.feature_names = self.core.feature_names

    def run_generation(self, config):
        metrics = {"f1": [], "sigs": [], "density": [], "precision": [], "recall": [], "score": [], "signal_map": []}
        train_end = int(len(self.lake) * self.oos_boundary)

        self.core.gene_scores *= self.decay_factor
        self.core.gene_usage *= self.decay_factor

        for i in range(0, self.core.pop_size, self.chunk_size):
            end_i = min(i + self.chunk_size, self.core.pop_size)
            curr_chunk = end_i - i

            indices = self.core.population[i:end_i]
            x_train = self.lake[:train_end, indices].permute(1, 0, 2)
            y_train = self.y_all[:, :train_end, :].expand(curr_chunk, -1, -1)

            w1 = self.core.pop_W1[i:end_i].detach().requires_grad_(True)
            b1 = self.core.pop_B1[i:end_i].detach().requires_grad_(True)
            w2 = self.core.pop_W2[i:end_i].detach().requires_grad_(True)
            b2 = self.core.pop_B2[i:end_i].detach().requires_grad_(True)

            optimizer = optim.Adam([w1, b1, w2, b2], lr=0.0005)

            for _ in range(self.epochs):
                optimizer.zero_grad()
                logits = self.core.forward(x_train, w1, b1, w2, b2)
                main_loss = self.lens.forward(logits, y_train)
                
                target_mean = torch.tensor(self.target_density, device=self.device)
                current_mean = torch.sigmoid(logits).mean()
                
                kl_penalty = self.penalty_coeff * (
                    current_mean * torch.log(current_mean / target_mean + 1e-8) +
                    (1 - current_mean) * torch.log((1 - current_mean) / (1 - target_mean + 1e-8) + 1e-8)
                )
                b2_penalty = 0.001 * torch.abs(b2).mean()
                
                loss = main_loss + kl_penalty + b2_penalty
                loss.backward()

                # --- PROTECT GLOBAL ELITES ---
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

            with torch.no_grad():
                self.core.pop_W1[i:end_i].copy_(w1)
                self.core.pop_B1[i:end_i].copy_(b1)
                self.core.pop_W2[i:end_i].copy_(w2)
                self.core.pop_B2[i:end_i].copy_(b2)

                x_oos = self.lake[train_end:, indices].permute(1, 0, 2)
                y_oos = self.y_all[:, train_end:, :].expand(curr_chunk, -1, -1)
                oos_probs = torch.sigmoid(self.core.forward(x_oos, w1, b1, w2, b2))

                best_score = torch.full((curr_chunk,), -1e9, device=self.device)
                best_f1 = torch.zeros(curr_chunk, device=self.device)
                best_thresh = torch.full((curr_chunk,), 0.40, device=self.device)
                best_sigs = torch.zeros(curr_chunk, device=self.device)
                best_prec = torch.zeros(curr_chunk, device=self.device)
                best_rec = torch.zeros(curr_chunk, device=self.device)
                best_preds = torch.zeros_like(oos_probs, device=self.device)

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

                    score = f1 * torch.clamp(torch.pow(prec, self.precision_exp), max=5.0)

                    min_density = self.min_sigs / oos_probs.shape[1]
                    dev_high = torch.relu(density - self.target_density * 1.5) * 15.0
                    dev_low = torch.relu(min_density * 0.8 - density) * 6.0
                    score = score - (dev_high + dev_low)

                    score = torch.where((sig_count >= self.min_sigs) & (prec > 0.02), score, torch.full_like(score, -1e9))

                    mask = score > best_score
                    best_score[mask] = score[mask]
                    best_f1[mask] = f1[mask]
                    best_thresh[mask] = t
                    best_sigs[mask] = sig_count[mask]
                    best_prec[mask] = prec[mask]
                    best_rec[mask] = rec[mask]
                    best_preds[mask] = preds[mask]

                self.core.thresholds[i:end_i] = best_thresh

                # Feature Impact Telemetry
                gene_imp = torch.bmm(w1.abs(), w2.abs()).squeeze(-1)
                imp_norm = gene_imp / (gene_imp.sum(dim=1, keepdim=True) + 1e-7)
                norm_scores = (best_score - best_score.min()) / (best_score.max() - best_score.min() + 1e-8)

                self.core.gene_scores.scatter_add_(0, indices.view(-1), (imp_norm * norm_scores.view(-1, 1)).reshape(-1))
                self.core.gene_usage.scatter_add_(0, indices.view(-1), torch.ones(indices.numel(), device=self.device))

                metrics["f1"].append(best_f1.detach().cpu())
                metrics["sigs"].append(best_sigs.detach().cpu())
                metrics["density"].append((best_sigs / oos_probs.shape[1]).detach().cpu())
                metrics["precision"].append(best_prec.detach().cpu())
                metrics["recall"].append(best_rec.detach().cpu())
                metrics["score"].append(best_score.detach().cpu())
                metrics["signal_map"].append(best_preds.squeeze(-1).detach().cpu())

        res = {k: torch.cat(v) for k, v in metrics.items()}
        self.latest_f1 = res["f1"].clone()
        self.latest_score = res["score"].clone()
        self.latest_precision = res["precision"].clone()

        # Dave decision
        self._pending_save = False
        if self.latest_f1 is not None:
            gen_best_idx = torch.argmax(self.latest_f1).item()
            gen_best_f1 = self.latest_f1[gen_best_idx].item()
            gen_best_prec = self.latest_precision[gen_best_idx].item()

            should_save = False
            reason = ""

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

    def run_atomic_scan(self):
        """Pass-through to Core logic."""
        self.core.run_atomic_scan()

    def evolve(self, metrics):
        """Delegates purely genetic logic to the Core."""
        self.core.evolve(self.latest_f1, self.latest_score)
        # Keep proxy properties in sync for Flight
        self.population = self.core.population

    def emit(self, features: pd.DataFrame) -> np.ndarray:
        return self.core.emit(features)

    def save_state(self, universe, filename: str, winner_idx: Optional[int] = None):
        """
        Saves the current best model state to disk.
        - Uses pending fields if a save was queued in run_generation.
        - Aborts immediately if no pending save (decision already made upstream).
        """
        if not hasattr(self, '_pending_save') or not self._pending_save:
            if self.verbose:
                self.print("PULSAR_SAVE_ABORT", reason="no pending save queued")
            return

        # Use only pending fields (set in run_generation)
        current_best_f1  = self._pending_save_f1
        current_best_prec = self._pending_save_prec
        winner_idx       = self._pending_save_idx if winner_idx is None else winner_idx

        # Clear pending flag
        self._pending_save = False

        if self.verbose:
            self.print(
                "PULSAR_SAVE_PENDING",
                f1=current_best_f1,
                prec=current_best_prec,
                winner_idx=winner_idx
            )

        # Proceed with save
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

        # Optional Redshift normalizer stats (unchanged)
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

    def state_dict(self):
        return {
            'population': self.core.population.detach().cpu(),
            'gene_scores': self.core.gene_scores.detach().cpu(),
            'gene_usage': self.core.gene_usage.detach().cpu(),
            'config': self.config,
            'feature_names': self.core.feature_names,
        }