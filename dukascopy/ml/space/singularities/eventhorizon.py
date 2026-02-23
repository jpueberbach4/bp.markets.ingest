import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, Optional

from ml.space.space import Singularity
from ml.space.lenses.spectograph import Spectrograph
from ml.space.space import Flight

class EventHorizonSingularity(Singularity):
    """
    1.4.8 Fix and polish: elite preservation fix. This is hard stuff. Brr
    """

    def __init__(self, config):
        
        super().__init__(device=config.get('device'))
        self.config = config
        
        self.pop_size = 1200
        self.gene_count = 16
        self.hidden_dim = 128
        self.decay_factor = 0.9
        
        self.spectrograph = Spectrograph(mode="focal", alpha=0.99, gamma=2.0)
        
        self.population = None  
        self.thresholds = None
        self.pop_W1 = None; self.pop_B1 = None
        self.pop_W2 = None; self.pop_B2 = None
        
        self.gene_scores = None
        self.gene_usage = None
        self.feature_names = None
        
        self.global_best_f1 = -1.0
        self.latest_f1 = None
        self.latest_score = None

    def compress(self, universe):
        self.universe = universe
        feature_df, target_series = universe.bigbang()
        num_indicators = len(feature_df.columns)
        self.feature_names = list(feature_df.columns)
        
        vals = np.nan_to_num(feature_df.values.astype(np.float32))
        self.lake = torch.tensor(vals, device=self.device)
        self.y_all = torch.tensor(target_series.values.astype(np.float32), device=self.device).view(1, -1, 1)

        self.population = torch.stack([
            torch.tensor(np.random.choice(num_indicators, self.gene_count, replace=False), device=self.device) 
            for _ in range(self.pop_size)
        ]).long()

        self.pop_W1 = torch.randn(self.pop_size, self.gene_count, self.hidden_dim, device=self.device) * np.sqrt(2.0 / self.gene_count)
        self.pop_B1 = torch.zeros(self.pop_size, 1, self.hidden_dim, device=self.device)
        self.pop_W2 = torch.randn(self.pop_size, self.hidden_dim, 1, device=self.device) * np.sqrt(2.0 / self.hidden_dim)
        self.pop_B2 = torch.full((self.pop_size, 1, 1), -2.0, device=self.device) 
        
        self.thresholds = torch.full((self.pop_size,), 0.40, device=self.device)
        self.gene_scores = torch.zeros(num_indicators, device=self.device)
        self.gene_usage = torch.zeros(num_indicators, device=self.device)

    def _forward(self, x, w1, b1, w2, b2):
        h1 = F.gelu(torch.bmm(x, w1) + b1)
        return torch.bmm(h1, w2) + b2

    def wormhole(self, flight: Flight ):
        # patch function, change
        print(f"🛰️ [Space]: Event Horizon expanded. New Flight path locked.")
        self.config = {**self.config, **(flight.config.get('settings') or {})}
        return self

    def run_generation(self, config):

        self.pop_size = 1200
        self.gene_count = 16
        self.hidden_dim = 128
        self.decay_factor = 0.9


        chunk_size = int(self.config.get("gpu_chunk", 256))
        min_sigs = int(self.config.get("min_signals", 3))
        target_density = float(self.config.get("target_density", 0.01))
        precision_exp = float(self.config.get("precision_exp", 2.5))
        penalty_coeff = float(self.config.get("penalty_coeff", 1.0))
        thresh_steps = int(self.config.get("thresh_steps", 31))
        verbose = bool(self.config.get("verbose", True))
        
        metrics = {"f1": [], "sigs": [], "density": [], "precision": [], "recall": [], "score": []}
        train_end = int(len(self.lake) * float(self.config.get("oos_boundary", 0.75)))
        
        self.gene_scores *= self.decay_factor
        self.gene_usage *= self.decay_factor

        for i in range(0, self.pop_size, chunk_size):
            end_i = min(i + chunk_size, self.pop_size)
            curr_chunk = end_i - i
            indices = self.population[i:end_i]

            x_train = self.lake[:train_end, indices].permute(1, 0, 2)
            y_train = self.y_all[:, :train_end, :].expand(curr_chunk, -1, -1)

            w1, b1 = self.pop_W1[i:end_i].detach().requires_grad_(True), self.pop_B1[i:end_i].detach().requires_grad_(True)
            w2, b2 = self.pop_W2[i:end_i].detach().requires_grad_(True), self.pop_B2[i:end_i].detach().requires_grad_(True)
            optimizer = optim.Adam([w1, b1, w2, b2], lr=0.0005)

            for _ in range(int(self.config.get("epochs", 25))):
                optimizer.zero_grad()
                logits = self._forward(x_train, w1, b1, w2, b2)
                loss = self.spectrograph.analyze(logits, y_train) + (torch.sigmoid(logits).mean() * penalty_coeff)
                loss.backward()

                if i == 0:
                    w1.grad[:2] = 0
                    b1.grad[:2] = 0
                    w2.grad[:2] = 0
                    b2.grad[:2] = 0

                torch.nn.utils.clip_grad_norm_([w1, b1, w2, b2], max_norm=1.0)
                optimizer.step()

            with torch.no_grad():
                self.pop_W1[i:end_i].copy_(w1); self.pop_B1[i:end_i].copy_(b1)
                self.pop_W2[i:end_i].copy_(w2); self.pop_B2[i:end_i].copy_(b2)

                x_oos = self.lake[train_end:, indices].permute(1, 0, 2)
                y_oos = self.y_all[:, train_end:, :].expand(curr_chunk, -1, -1)
                oos_probs = torch.sigmoid(self._forward(x_oos, w1, b1, w2, b2))

                best_score = torch.full((curr_chunk,), -1e9, device=self.device)
                best_f1, best_thresh, best_sigs = torch.zeros(curr_chunk, device=self.device), torch.full((curr_chunk,), 0.40, device=self.device), torch.zeros(curr_chunk, device=self.device)
                best_prec, best_rec = torch.zeros(curr_chunk, device=self.device), torch.zeros(curr_chunk, device=self.device)

                for t in torch.linspace(0.15, 0.85, thresh_steps):
                    preds = (oos_probs > t).float()
                    sig_count, density = preds.sum(dim=1).view(-1), preds.mean(dim=1).view(-1)
                    tp = (preds * y_oos).sum(dim=1).view(-1)
                    fp = (preds * (1 - y_oos)).sum(dim=1).view(-1)
                    fn = ((1 - preds) * y_oos).sum(dim=1).view(-1)
                    
                    prec, rec = tp / (tp + fp + 1e-8), tp / (tp + fn + 1e-8)
                    f1 = 2 * prec * rec / (prec + rec + 1e-8)
                    score = f1 * torch.clamp(torch.pow(prec, precision_exp), max=5.0)
                    
                    min_density = min_sigs / oos_probs.shape[1]
                    dev_high = torch.relu(density - target_density * 1.5) * 15.0
                    dev_low = torch.relu(min_density * 0.8 - density) * 6.0
                    score = score - (dev_high + dev_low)
                    
                    score = torch.where(sig_count >= min_sigs, score, torch.full_like(score, -1e9))
                    mask = score > best_score
                    best_score[mask], best_f1[mask], best_thresh[mask], best_sigs[mask] = score[mask], f1[mask], t, sig_count[mask]
                    best_prec[mask], best_rec[mask] = prec[mask], rec[mask]

                if verbose:
                    print(f"Chunk {i//chunk_size} | MaxP: {oos_probs.max():.3f} | BestSigs: {best_sigs.max().item():.0f} | F1: {best_f1.max():.4f}")

                self.thresholds[i:end_i] = best_thresh
                
                gene_imp = torch.bmm(w1.abs(), w2.abs()).squeeze(-1) 
                imp_norm = gene_imp / (gene_imp.sum(dim=1, keepdim=True) + 1e-7)
                
                score_range = best_score.max() - best_score.min()
                if score_range > 0.01:
                    norm_scores = (best_score - best_score.min()) / (score_range + 1e-8)
                else:
                    norm_scores = torch.ones_like(best_score)
                    
                self.gene_scores.scatter_add_(0, indices.view(-1), (imp_norm * norm_scores.view(-1, 1)).reshape(-1))
                self.gene_usage.scatter_add_(0, indices.view(-1), torch.ones(indices.numel(), device=self.device))

                metrics["f1"].append(best_f1.detach().cpu())
                metrics["sigs"].append(best_sigs.detach().cpu())
                metrics["density"].append((best_sigs / oos_probs.shape[1]).detach().cpu())
                metrics["precision"].append(best_prec.detach().cpu())
                metrics["recall"].append(best_rec.detach().cpu())
                metrics["score"].append(best_score.detach().cpu())

        res = {k: torch.cat(v) for k, v in metrics.items()}
        self.latest_f1 = res["f1"].clone()
        self.latest_score = res["score"].clone()
        return res

    def run_atomic_scan(self, top_n_vitality=40):
        vitality = (self.gene_scores + 0.1) / (self.gene_usage + 1.0)
        pool = torch.argsort(vitality, descending=True)[:top_n_vitality]
        start_idx = int(self.pop_size * 0.8)
        
        for i in range(start_idx, self.pop_size):
            self.population[i] = pool[torch.randperm(len(pool))[:self.gene_count]].to(self.device)
            self.pop_W1[i] = torch.randn(self.gene_count, self.hidden_dim, device=self.device) * np.sqrt(2.0/self.gene_count)
            self.pop_W2[i] = torch.randn(self.hidden_dim, 1, device=self.device) * np.sqrt(2.0/self.hidden_dim)
            self.pop_B2[i] = -2.0 

    def evolve(self, fitness_scores):
        f1_scores = self.latest_f1.to(self.device).flatten()
        primary_scores = self.latest_score.to(self.device).flatten()
        
        gen_best_f1_val, gen_best_f1_idx = torch.max(f1_scores, dim=0)

        champ_pop = self.population[gen_best_f1_idx].clone()
        champ_w1, champ_b1 = self.pop_W1[gen_best_f1_idx].clone(), self.pop_B1[gen_best_f1_idx].clone()
        champ_w2, champ_b2 = self.pop_W2[gen_best_f1_idx].clone(), self.pop_B2[gen_best_f1_idx].clone()
        champ_thresh = self.thresholds[gen_best_f1_idx].clone()
        
        idx = torch.argsort(primary_scores, descending=True)
        self.population, self.thresholds = self.population[idx], self.thresholds[idx]
        self.pop_W1, self.pop_B1 = self.pop_W1[idx], self.pop_B1[idx]
        self.pop_W2, self.pop_B2 = self.pop_W2[idx], self.pop_B2[idx]

        if gen_best_f1_val > self.global_best_f1:
            if bool(self.config.get("verbose", True)):
                print(f"🔥 [Evolution]: New F1 High-Water Mark: {gen_best_f1_val:.4f} (Global Best was {self.global_best_f1:.4f})")
            self.global_best_f1 = gen_best_f1_val.item()
        
        keep = max(2, self.pop_size // 10)
        new_pop = self.population.clone()
        new_w1, new_b1 = self.pop_W1.clone(), self.pop_B1.clone()
        new_w2, new_b2 = self.pop_W2.clone(), self.pop_B2.clone()
        new_thresh = self.thresholds.clone()
        
        if gen_best_f1_val > f1_scores[idx[0]]:
            new_pop[0] = champ_pop
            new_w1[0], new_b1[0] = champ_w1, champ_b1
            new_w2[0], new_b2[0] = champ_w2, champ_b2
            new_thresh[0] = champ_thresh
        else:
            new_pop[1] = champ_pop
            new_w1[1], new_b1[1] = champ_w1, champ_b1
            new_w2[1], new_b2[1] = champ_w2, champ_b2
            new_thresh[1] = champ_thresh

        mutation_std = float(self.config.get("weight_mutation_rate", 0.005))

        for i in range(keep, self.pop_size):
            p1, p2 = torch.randint(0, keep, (2,))
            if torch.rand(1).item() < 0.7: 
                cut = torch.randint(0, self.gene_count, (1,)).item()
                new_pop[i, :cut], new_pop[i, cut:] = self.population[p1, :cut], self.population[p2, cut:]
                alpha = torch.rand(1, device=self.device) * 0.2 + 0.4
                new_w1[i] = alpha * self.pop_W1[p1] + (1-alpha) * self.pop_W1[p2]
                new_w2[i] = alpha * self.pop_W2[p1] + (1-alpha) * self.pop_W2[p2]
                new_thresh[i] = alpha * self.thresholds[p1] + (1-alpha) * self.thresholds[p2]
            else: 
                new_pop[i] = self.population[p1].clone()
                new_w1[i] = self.pop_W1[p1] + torch.randn_like(self.pop_W1[p1]) * mutation_std
                new_w2[i] = self.pop_W2[p1] + torch.randn_like(self.pop_W2[p1]) * mutation_std
                new_thresh[i] = self.thresholds[p1] + torch.randn(1, device=self.device).squeeze() * 0.01

        self.population = new_pop
        self.pop_W1, self.pop_B1 = new_w1, new_b1
        self.pop_W2, self.pop_B2 = new_w2, new_b2
        self.thresholds = torch.clamp(new_thresh, 0.10, 0.85)
        
        self.run_atomic_scan(top_n_vitality=40)

    def emit(self, features: pd.DataFrame) -> np.ndarray:
        if len(features) == 0: return np.array([])
        with torch.no_grad():
            x = torch.tensor(features.values.astype(np.float32), device=self.device)
            x_sel = x[:, self.population[0]].unsqueeze(0)
            logits = self._forward(x_sel, self.pop_W1[0:1], self.pop_B1[0:1], self.pop_W2[0:1], self.pop_B2[0:1])
            return (torch.sigmoid(logits) > self.thresholds[0]).cpu().numpy().flatten()

    def save_state(self, universe, filename: str, winner_idx: Optional[int] = None):
        if winner_idx is None:
            if self.latest_f1 is not None:
                winner_idx = torch.argmax(self.latest_f1).item()
            else:
                winner_idx = 0
                
        winner_genes = self.population[winner_idx].cpu().tolist()
        atomic_feature_map = [self.feature_names[i] for i in winner_genes]
        state = {
            'population': torch.arange(len(atomic_feature_map)), 
            'threshold': self.thresholds[winner_idx].cpu(),
            'W1': self.pop_W1[winner_idx].cpu(), 
            'B1': self.pop_B1[winner_idx].cpu(),
            'W2': self.pop_W2[winner_idx].cpu(), 
            'B2': self.pop_B2[winner_idx].cpu(),
            'feature_names': atomic_feature_map, 
            'config': self.config
        }
        universe.eject(filename, state, is_model=True)
        if bool(self.config.get("verbose", True)):
            print(f"🥇 [Singularity]: Atomic Winner Ejected. Features: {len(atomic_feature_map)}")

    def state_dict(self):
        return {
            'population': self.population.detach().cpu(),
            'gene_scores': self.gene_scores.detach().cpu(),
            'gene_usage': self.gene_usage.detach().cpu(),
            'config': self.config,
            'feature_names': self.feature_names
        }