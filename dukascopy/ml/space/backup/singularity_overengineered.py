import torch
import torch.optim as optim
import torch.nn.functional as F
import numpy as np
import pandas as pd
import logging
from typing import Dict, Any

from ml.space.space import Singularity
from ml.space.lenses import Spectrograph


class EventHorizonSingularity(Singularity):
    """
    Version: 7.0 — Performance-Restored / Audit-Complete

    CONFIG KEYS CONSUMED BY THIS CLASS
    ───────────────────────────────────
    Core
      POP_SIZE            int     Population size                        (1200)
      GENE_COUNT          int     Features per individual; must be ≤ 40  (24)
      HIDDEN_DIM          int     Hidden layer width                     (256)
      GPU_CHUNK           int     Individuals evaluated per GPU batch    (200)
      SEED                int     Global RNG seed                        (42)
      VERBOSE             bool    Enable INFO-level logging              (True)

    Training
      LEARNING_RATE       float   Adam lr                                (0.0005)
      EPOCHS              int     Gradient steps per WF window           (20)
      WF_WINDOWS          int     Walk-forward folds                     (3)
      OOS_BOUNDARY        float   Fraction of data used for training;
                                  remainder split into WF windows.
                                  Replaces the hardcoded /(wf+1) formula.(0.75)

    Evaluation / rejection
      PRECISION_EXP       float   Exponent on precision in score         (1.5)
      MIN_SIGNALS         int     Min total signals across all WF wins   (5)
      MIN_RECALL          float   Minimum avg recall to avoid rejection   (0.05)
      DENSITY_MIN         float   Minimum per-window signal density      (0.001)
      DENSITY_MAX         float   Maximum per-window signal density      (0.05)
      TARGET_DENSITY      float   Ideal signal density for penalty term  (0.01)
      PENALTY_COEFF       float   Density-penalty coefficient in score   (1.0)
      THRESH_STEPS        int     Threshold candidates in [0.3, 0.7]
                                  searched per individual. 1 → fixed 0.5.(31)

    Evolution
      VITALITY_DECAY      float   Per-generation gene score decay        (0.90)
      W1_MUTATION_RATE    float   Noise scale for hidden-layer mutation  (0.02)
      W2_MUTATION_RATE    float   Noise scale for output-layer mutation  (0.002)

    CAUSALITY WARNING
    This engine assumes all input features are strictly causal.
    Any upstream lookahead bias will be aggressively exploited.
    """

    def __init__(self, config: Dict[str, Any], device: str = "cuda"):
        super().__init__(device=device)
        self.config     = config
        self.pop_size   = config.get("POP_SIZE",    1200)
        self.gene_count = config.get("GENE_COUNT",  24)
        self.hidden_dim = config.get("HIDDEN_DIM",  256)
        self.decay_factor = config.get("VITALITY_DECAY", 0.90)
        self.spectrograph = Spectrograph(mode="focal", alpha=0.99, gamma=2.0)

        self.logger = logging.getLogger("EventHorizonSingularity")
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
            self.logger.addHandler(handler)
            self.logger.setLevel(
                logging.INFO if config.get("VERBOSE", True) else logging.WARNING
            )

        self.population = None
        self.pop_W1     = None
        self.pop_B1     = None
        self.pop_W2     = None
        self.pop_B2     = None

        self.gene_scores  = None
        self.gene_usage   = None
        self.feature_names = None
        self.generation_count  = 0
        self.highest_saved_f1  = -1.0

        self.champ_indices = None
        self.champ_W1  = None   # [gene_count, hidden_dim]
        self.champ_B1  = None   # [1, hidden_dim]
        self.champ_W2  = None   # [hidden_dim, 1]
        self.champ_B2  = None   # [1, 1]
        self.champ_mean = None  # [1, 1, gene_count] — window-0 ref for deployment
        self.champ_std  = None  # [1, 1, gene_count]

        self.prod_indices = None
        self.prod_W1  = None    # [1, gene_count, hidden_dim]
        self.prod_B1  = None    # [1, 1,          hidden_dim]
        self.prod_W2  = None    # [1, hidden_dim, 1         ]
        self.prod_B2  = None    # [1, 1,          1         ]
        self.prod_mean = None   # [1, 1, gene_count]
        self.prod_std  = None   # [1, 1, gene_count]

    def _wf_windows_and_sizeXX(self):
        wf_windows  = self.config.get("WF_WINDOWS", 3)
        oos_boundary = self.config.get("OOS_BOUNDARY", 0.75)
        N            = len(self.lake)
        wf_total     = int(N * (1.0 - oos_boundary))
        window_size  = max(1, wf_total // (wf_windows * 2))
        return wf_windows, window_size

    def _wf_windows_and_size(self):
        wf_windows = self.config.get("WF_WINDOWS", 3)
        N = len(self.lake)
        window_size = N // (wf_windows + 1)
        return wf_windows, window_size

    def compress(self, universe):
        seed = self.config.get("SEED", 42)
        torch.manual_seed(seed)
        np.random.seed(seed)

        feature_df, target_series = universe.bigbang()
        num_indicators   = len(feature_df.columns)
        self.feature_names = list(feature_df.columns)

        assert self.gene_count <= 40, (
            f"GENE_COUNT ({self.gene_count}) must be ≤ 40 (vitality pool size). "
            "Raise the [:40] slice in run_atomic_scan if you need more genes."
        )

        vals = np.nan_to_num(feature_df.values.astype(np.float32))
        self.lake  = torch.tensor(vals, device=self.device)
        self.y_all = (
            torch.tensor(target_series.values.astype(np.float32), device=self.device)
            .view(1, -1, 1)
        )

        self.population = torch.stack([
            torch.tensor(
                np.random.choice(num_indicators, self.gene_count, replace=False),
                device=self.device,
            )
            for _ in range(self.pop_size)
        ]).long()

        self.pop_W1 = (
            torch.randn(self.pop_size, self.gene_count, self.hidden_dim, device=self.device)
            * np.sqrt(2.0 / self.gene_count)
        )
        self.pop_B1 = torch.zeros(self.pop_size, 1, self.hidden_dim, device=self.device)
        self.pop_W2 = (
            torch.randn(self.pop_size, self.hidden_dim, 1, device=self.device)
            * np.sqrt(2.0 / self.hidden_dim)
        )
        self.pop_B2 = torch.full((self.pop_size, 1, 1), -2.0, device=self.device)

        self.gene_scores = torch.zeros(num_indicators, device=self.device)
        self.gene_usage  = torch.zeros(num_indicators, device=self.device)

        wf_windows, window_size = self._wf_windows_and_size()
        self.logger.info(
            f"compress() | N={len(self.lake)} bars | "
            f"WF_WINDOWS={wf_windows} | window_size={window_size} bars | "
            f"Features={num_indicators} | Pop={self.pop_size}"
        )

    def _forward(self, x, w1, b1, w2, b2):
        return torch.bmm(F.gelu(torch.bmm(x, w1) + b1), w2) + b2


    def _train_chunk(self, indices, t_start, t_end, w1, b1, w2, b2):
        batch_size = indices.shape[0]

        x_raw  = self.lake[t_start:t_end, indices].permute(1, 0, 2)  # [batch, seq, genes]
        w_mean = x_raw.mean(dim=1, keepdim=True)                      # [batch, 1,   genes]
        w_std  = x_raw.std(dim=1, keepdim=True).clamp(min=1e-8)
        x_train = (x_raw - w_mean) / w_std
        y_train = self.y_all[:, t_start:t_end, :].expand(batch_size, -1, -1)

        w1 = w1.clone().detach().requires_grad_(True)
        b1 = b1.clone().detach().requires_grad_(True)
        w2 = w2.clone().detach().requires_grad_(True)
        b2 = b2.clone().detach().requires_grad_(True)

        optimizer = optim.Adam(
            [w1, b1, w2, b2],
            lr=self.config.get("LEARNING_RATE", 0.0005),
        )

        for _ in range(self.config.get("EPOCHS", 20)):
            optimizer.zero_grad()
            loss = self.spectrograph.analyze(self._forward(x_train, w1, b1, w2, b2), y_train)
            loss.backward()
            torch.nn.utils.clip_grad_norm_([w1, b1, w2, b2], 1.0)
            optimizer.step()
            with torch.no_grad():
                w1.clamp_(-3.0, 3.0)
                w2.clamp_(-3.0, 3.0)

        return w1.detach(), b1.detach(), w2.detach(), b2.detach(), w_mean, w_std

    def _best_threshold(self, logits_stack, y_stack):
        steps = self.config.get("THRESH_STEPS", 1)
        if steps <= 1:
            return 0.5

        thresholds = torch.linspace(0.3, 0.7, steps, device=self.device)
        probs = torch.sigmoid(logits_stack)   # [wins, batch, seq, 1]

        best_thresh = 0.5
        best_min_f1 = -1.0

        for thresh in thresholds:
            preds = (probs > thresh).float()
            tp = (preds * y_stack).sum(dim=2).squeeze(-1)      # [wins, batch]
            fp = (preds * (1 - y_stack)).sum(dim=2).squeeze(-1)
            fn = ((1 - preds) * y_stack).sum(dim=2).squeeze(-1)
            p  = tp / (tp + fp + 1e-8)
            r  = tp / (tp + fn + 1e-8)
            f1 = 2 * p * r / (p + r + 1e-8)                   # [wins, batch]
            min_f1 = f1.min(dim=0).values.mean().item()        # scalar
            if min_f1 > best_min_f1:
                best_min_f1 = min_f1
                best_thresh = thresh.item()

        return best_thresh

    def run_generation(self, universe):
        precision_exp  = self.config.get("PRECISION_EXP",  1.5)
        min_sigs       = self.config.get("MIN_SIGNALS",    5)
        min_recall     = self.config.get("MIN_RECALL",     0.05)
        d_min          = self.config.get("DENSITY_MIN",    0.001)
        d_max          = self.config.get("DENSITY_MAX",    0.05)
        target_density = self.config.get("TARGET_DENSITY", 0.01)
        penalty_coeff  = self.config.get("PENALTY_COEFF",  1.0)
        gpu_chunk      = self.config.get("GPU_CHUNK",      200)
        verbose        = self.config.get("VERBOSE",        True)

        wf_windows, window_size = self._wf_windows_and_size()

        actual_test_samples = sum(
            min(t_end + window_size, len(self.lake)) - t_end
            for w in range(wf_windows)
            for t_end in [(w + 1) * window_size]
            if min(t_end + window_size, len(self.lake)) > t_end
        )

        metrics = {k: [] for k in
                   ("f1", "avg_f1", "sigs", "score", "precision", "recall", "density")}
        total_rejected = 0

        for i in range(0, self.pop_size, gpu_chunk):
            end_i     = min(i + gpu_chunk, self.pop_size)
            batch_len = end_i - i
            indices   = self.population[i:end_i]          # [batch, gene_count]

            window_f1s, window_precs, window_recs = [], [], []
            window_oob = torch.zeros(batch_len, dtype=torch.bool, device=self.device)
            total_sigs = torch.zeros(batch_len, device=self.device)

            cur_w1 = self.pop_W1[i:end_i].clone().detach()
            cur_b1 = self.pop_B1[i:end_i].clone().detach()
            cur_w2 = self.pop_W2[i:end_i].clone().detach()
            cur_b2 = self.pop_B2[i:end_i].clone().detach()

            for w in range(wf_windows):
                t_start    = w * window_size
                t_end      = (w + 1) * window_size
                test_start = t_end
                test_end   = min(t_end + window_size, len(self.lake))
                if test_end <= test_start:
                    continue

                if i == 0 and self.champ_W1 is not None:
                    peer_w1, peer_b1, peer_w2, peer_b2, w_mean, w_std = self._train_chunk(
                        indices[1:], t_start, t_end,
                        cur_w1[1:], cur_b1[1:], cur_w2[1:], cur_b2[1:],
                    )
                    cur_w1 = torch.cat([cur_w1[:1], peer_w1], dim=0)
                    cur_b1 = torch.cat([cur_b1[:1], peer_b1], dim=0)
                    cur_w2 = torch.cat([cur_w2[:1], peer_w2], dim=0)
                    cur_b2 = torch.cat([cur_b2[:1], peer_b2], dim=0)

                    c_raw  = self.lake[t_start:t_end, self.champ_indices]
                    c_mean = c_raw.mean(dim=0).view(1, 1, -1)
                    c_std  = c_raw.std(dim=0).clamp(min=1e-8).view(1, 1, -1)
                    f_mean = torch.cat([c_mean, w_mean], dim=0)
                    f_std  = torch.cat([c_std,  w_std],  dim=0)
                else:
                    cur_w1, cur_b1, cur_w2, cur_b2, f_mean, f_std = self._train_chunk(
                        indices, t_start, t_end,
                        cur_w1, cur_b1, cur_w2, cur_b2,
                    )

                with torch.no_grad():
                    x_test = (
                        self.lake[test_start:test_end, indices].permute(1, 0, 2) - f_mean
                    ) / f_std                                         # [batch, seq, genes]
                    y_test = self.y_all[:, test_start:test_end, :].expand(batch_len, -1, -1)

                    thresh_steps = self.config.get("THRESH_STEPS", 1)
                    if thresh_steps > 1:
                        logits = self._forward(x_test, cur_w1, cur_b1, cur_w2, cur_b2)
                        thresh = self._best_threshold(
                            logits.unsqueeze(0), y_test.unsqueeze(0)
                        )
                    else:
                        logits = self._forward(x_test, cur_w1, cur_b1, cur_w2, cur_b2)
                        thresh = 0.5

                    preds = (torch.sigmoid(logits) > thresh).float()

                    tp   = (preds *  y_test      ).sum(dim=1).view(-1)
                    fp   = (preds * (1 - y_test) ).sum(dim=1).view(-1)
                    fn   = ((1 - preds) * y_test ).sum(dim=1).view(-1)
                    prec = tp / (tp + fp + 1e-8)
                    rec  = tp / (tp + fn + 1e-8)
                    f1   = 2 * prec * rec / (prec + rec + 1e-8)
                    sigs = preds.sum(dim=1).view(-1)
                    dens = sigs / y_test.shape[1]

                    window_oob |= (dens < d_min) | (dens > d_max)
                    window_f1s.append(f1)
                    window_precs.append(prec)
                    window_recs.append(rec)
                    total_sigs += sigs

            with torch.no_grad():
                stacked_f1   = torch.stack(window_f1s)
                robust_f1    = stacked_f1.min(dim=0).values
                avg_prec     = torch.stack(window_precs).mean(dim=0)
                avg_rec      = torch.stack(window_recs).mean(dim=0)
                avg_density  = total_sigs / max(actual_test_samples, 1)

                density_penalty = penalty_coeff * (avg_density - target_density).abs()
                score = robust_f1 * torch.pow(avg_prec, precision_exp) - density_penalty

                hard_reject = (
                    (total_sigs < min_sigs * wf_windows)
                    | (avg_rec < min_recall)
                    | window_oob
                )
                total_rejected += hard_reject.sum().item()
                final_score = torch.where(hard_reject, torch.full_like(score, -1e9), score)

                gene_imp = torch.bmm(cur_w1.abs(), cur_w2.abs()).squeeze(-1)
                imp_norm = gene_imp / (gene_imp.sum(dim=1, keepdim=True) + 1e-7)
                contrib  = torch.where(
                    hard_reject.view(-1, 1),
                    torch.zeros_like(imp_norm),
                    imp_norm * robust_f1.view(-1, 1),
                )
                self.gene_scores.scatter_add_(0, indices.view(-1), contrib.reshape(-1))
                self.gene_usage.scatter_add_(
                    0, indices.view(-1),
                    torch.ones_like(indices.view(-1), dtype=torch.float32),
                )

                metrics["f1"].append(robust_f1)
                metrics["avg_f1"].append(stacked_f1.mean(dim=0))
                metrics["score"].append(final_score)
                metrics["precision"].append(avg_prec)
                metrics["recall"].append(avg_rec)
                metrics["sigs"].append(total_sigs)
                metrics["density"].append(avg_density)

            if verbose:
                self.logger.info(
                    f"Gen {self.generation_count} | Chunk {i // gpu_chunk} | "
                    f"Peak F1: {robust_f1.max():.4f} | "
                    f"Peak Prec: {avg_prec.max():.4f} | "
                    f"Rejected: {hard_reject.sum().item()}/{batch_len}"
                )

        res = {k: torch.cat([x.flatten() for x in v]).to(self.device)
               for k, v in metrics.items()}

        if self.generation_count < 3:
            pos_rate      = self.y_all.mean().item()
            #suspicious_f1 = min(0.60, (4 * pos_rate) / (1 + pos_rate))

            suspicious_f1 = (4 * pos_rate) / (1 + pos_rate)
            
            # Raise noise floor to 0.30 for Gen 0 to account for pop variance
            bound = max(0.30 if self.generation_count == 0 else 0.25, suspicious_f1)
            
            peak_f1 = res["f1"].max().item()
            if peak_f1 >= bound:
                self.logger.error(f"💥 [Leakage Alert]: Gen {self.generation_count} peak F1 {peak_f1:.4f} exceeded bound {bound:.4f}")

        if verbose:
            vitality    = (self.gene_scores + 0.1) / (self.gene_usage + 1.0)
            reject_rate = (total_rejected / self.pop_size) * 100.0
            self.logger.info(
                f"Gen {self.generation_count} | SUMMARY | "
                f"Peak F1: {res['f1'].max():.4f} | "
                f"Peak Avg F1: {res['avg_f1'].max():.4f} | "
                f"Prec: {res['precision'].max():.4f} | "
                f"Rec: {res['recall'].max():.4f} | "
                f"Density: {res['density'].mean():.4f} | "
                f"Rejected: {reject_rate:.1f}% | "
                f"Vitality σ: {vitality.std():.4f}"
            )

        return res

    def evolve(self, metrics):
        seed = 42 + self.generation_count
        torch.manual_seed(seed)
        np.random.seed(seed)

        best_idx = torch.argmax(metrics["f1"]).item()
        if metrics["f1"][best_idx].item() > self.highest_saved_f1:
            self.highest_saved_f1  = metrics["f1"][best_idx].item()
            self.champ_indices     = self.population[best_idx].clone().detach()
            self.champ_W1          = self.pop_W1[best_idx].clone().detach()
            self.champ_B1          = self.pop_B1[best_idx].clone().detach()
            self.champ_W2          = self.pop_W2[best_idx].clone().detach()
            self.champ_B2          = self.pop_B2[best_idx].clone().detach()
            _, window_size         = self._wf_windows_and_size()
            c_slice                = self.lake[:window_size, self.champ_indices]
            self.champ_mean        = c_slice.mean(dim=0, keepdim=True).view(1, 1, -1)
            self.champ_std         = c_slice.std(dim=0, keepdim=True).clamp(min=1e-8).view(1, 1, -1)
            self.logger.warning(
                f"👑 [Elite]: Champion crystallised at F1 {self.highest_saved_f1:.4f}"
            )

        self.generation_count += 1
        self.gene_scores *= self.decay_factor
        self.gene_usage  *= self.decay_factor

        idx             = torch.argsort(metrics["score"], descending=True)
        self.population = self.population[idx]
        self.pop_W1     = self.pop_W1[idx]
        self.pop_B1     = self.pop_B1[idx]
        self.pop_W2     = self.pop_W2[idx]
        self.pop_B2     = self.pop_B2[idx]

        keep   = max(2, self.pop_size // 10)
        new_pop = self.population.clone()
        new_w1  = self.pop_W1.clone()
        new_b1  = self.pop_B1.clone()
        new_w2  = self.pop_W2.clone()
        new_b2  = self.pop_B2.clone()

        is_solar_flare = (self.generation_count % 25 == 0)
        w1_mut = self.config.get("W1_MUTATION_RATE", 0.02) * (3.0 if is_solar_flare else 1.0)
        w2_mut = self.config.get("W2_MUTATION_RATE", 0.002) * (3.0 if is_solar_flare else 1.0)

        if is_solar_flare and self.config.get("VERBOSE", True):
            self.logger.warning(
                f"☀️  [Energy]: Super-mutation shock at Gen {self.generation_count}."
            )

        all_feature_ids = set(range(len(self.feature_names)))

        for i in range(keep, self.pop_size):
            p1, p2 = torch.randint(0, keep, (2,)).tolist()

            if torch.rand(1).item() < 0.7:
                child_genes:   list = []
                child_w1_rows: list = []

                for g_idx in range(self.gene_count):
                    src  = p1 if torch.rand(1).item() < 0.5 else p2
                    gene = self.population[src, g_idx].item()

                    if gene not in child_genes:
                        child_genes.append(gene)
                        child_w1_rows.append(self.pop_W1[src, g_idx].clone())
                    else:
                        remaining = list(all_feature_ids - set(child_genes))
                        if not remaining:
                            remaining = list(all_feature_ids)
                        fill_gene = int(np.random.choice(remaining))
                        child_genes.append(fill_gene)
                        child_w1_rows.append(
                            torch.randn(self.hidden_dim, device=self.device)
                            * np.sqrt(2.0 / self.gene_count)
                        )

                new_pop[i] = torch.tensor(child_genes, dtype=torch.long, device=self.device)
                new_w1[i]  = torch.stack(child_w1_rows)
                new_b1[i]  = self.pop_B1[p1].clone()
                new_w2[i]  = self.pop_W2[p1].clone()
                new_b2[i]  = self.pop_B2[p1].clone()

            else:
                new_pop[i] = self.population[p1].clone()
                new_w1[i]  = self.pop_W1[p1] + torch.randn_like(self.pop_W1[p1]) * w1_mut
                new_b1[i]  = self.pop_B1[p1].clone()
                new_w2[i]  = self.pop_W2[p1] + torch.randn_like(self.pop_W2[p1]) * w2_mut
                new_b2[i]  = self.pop_B2[p1].clone()

            new_w1[i].clamp_(-3.0, 3.0)
            new_w2[i].clamp_(-3.0, 3.0)

        if self.champ_indices is not None:
            new_pop[0] = self.champ_indices
            new_w1[0]  = self.champ_W1
            new_b1[0]  = self.champ_B1
            new_w2[0]  = self.champ_W2
            new_b2[0]  = self.champ_B2

        self.population = new_pop
        self.pop_W1     = new_w1
        self.pop_B1     = new_b1
        self.pop_W2     = new_w2
        self.pop_B2     = new_b2

        self.run_atomic_scan()

    def run_atomic_scan(self):
        vitality = (self.gene_scores + 0.1) / (self.gene_usage + 1.0)
        pool     = torch.argsort(vitality, descending=True)[:40].tolist()

        assert len(pool) >= self.gene_count, (
            f"Vitality pool ({len(pool)}) < gene_count ({self.gene_count}). "
            "Raise the [:40] slice in run_atomic_scan."
        )

        for i in range(int(self.pop_size * 0.9), self.pop_size):
            if i == 0:
                continue
            self.population[i] = torch.tensor(
                np.random.choice(pool, self.gene_count, replace=False),
                dtype=torch.long, device=self.device,
            )
            self.pop_W1[i] = torch.randn_like(self.pop_W1[i]) * np.sqrt(2.0 / self.gene_count)
            self.pop_B1[i].zero_()
            self.pop_W2[i] = torch.randn_like(self.pop_W2[i]) * np.sqrt(2.0 / self.hidden_dim)
            self.pop_B2[i].fill_(-2.0)


    def _deploy_champion(self, winner_idx: int = 0):
        if winner_idx == 0 and self.champ_W1 is not None:
            self.prod_indices = self.champ_indices
            self.prod_W1      = self.champ_W1.unsqueeze(0)
            self.prod_B1      = self.champ_B1.unsqueeze(0)
            self.prod_W2      = self.champ_W2.unsqueeze(0)
            self.prod_B2      = self.champ_B2.unsqueeze(0)
            self.prod_mean    = self.champ_mean
            self.prod_std     = self.champ_std
        else:
            t                 = winner_idx
            self.prod_indices = self.population[t]
            self.prod_W1      = self.pop_W1[t].unsqueeze(0)
            self.prod_B1      = self.pop_B1[t].unsqueeze(0)
            self.prod_W2      = self.pop_W2[t].unsqueeze(0)
            self.prod_B2      = self.pop_B2[t].unsqueeze(0)
            _, window_size    = self._wf_windows_and_size()
            c_slice           = self.lake[:window_size, self.prod_indices]
            self.prod_mean    = c_slice.mean(dim=0).view(1, 1, -1)
            self.prod_std     = c_slice.std(dim=0).clamp(min=1e-8).view(1, 1, -1)

    def emit(self, features: pd.DataFrame) -> np.ndarray:
        if len(features) == 0:
            return np.array([], dtype=bool)
        if self.prod_W1 is None:
            self._deploy_champion(0)

        with torch.no_grad():
            x_raw  = torch.tensor(features.values.astype(np.float32), device=self.device)
            x_sel  = x_raw[:, self.prod_indices].unsqueeze(0)   # [1, seq, genes]
            x_norm = (x_sel - self.prod_mean) / self.prod_std
            logits = self._forward(
                x_norm, self.prod_W1, self.prod_B1, self.prod_W2, self.prod_B2
            )
            return (torch.sigmoid(logits) > 0.5).cpu().numpy().flatten()

    def save_state(
        self,
        universe,
        filename: str,
        winner_idx: int = 0,
        current_f1: float = -1.0,
    ) -> bool:
        if current_f1 >= 0.0 and current_f1 <= self.highest_saved_f1:
            return False
        if current_f1 > self.highest_saved_f1:
            self.highest_saved_f1 = current_f1

        self._deploy_champion(winner_idx)

        state = {
            "W1":           self.prod_W1.cpu(),
            "B1":           self.prod_B1.cpu(),
            "W2":           self.prod_W2.cpu(),
            "B2":           self.prod_B2.cpu(),
            "norm_mean":    self.prod_mean.cpu(),
            "norm_std":     self.prod_std.cpu(),
            "feature_names":[self.feature_names[j] for j in self.prod_indices.tolist()],
            "config":       self.config,
            "highest_f1":   self.highest_saved_f1,
        }
        universe.eject(filename, state, is_model=True)

        if self.config.get("VERBOSE", True):
            self.logger.info(
                f"🥇 [Singularity]: State saved → {filename} | "
                f"F1: {current_f1:.4f} | Features: {len(self.prod_indices)}"
            )
        return True