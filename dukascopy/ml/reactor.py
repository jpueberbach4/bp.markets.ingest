import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
import numpy as np
import threading
import queue
import os
import fnmatch
from itertools import combinations

# VERSION 5.7.2 - "GETTING-THERE" VERSION. ALMOST.
# LAZY VERSION.

log_queue = queue.Queue(maxsize=100)

def async_sink_worker():
    """Consumes data from the queue to decouple I/O from the GPU Flight path."""
    # Ensure directories exist so we don't crash on the first write
    os.makedirs('checkpoints', exist_ok=True)
    os.makedirs('logs', exist_ok=True)
    
    while True:
        item = log_queue.get()
        if item is None: break
        filename, data, is_model = item
        try:
            if is_model:
                torch.save(data, f"checkpoints/{filename}")
            else:
                with open("logs/evolution.log", "a") as f:
                    f.write(f"{data}\n")
        except Exception as e:
            print(f"❌ [Sink Error]: {e}")
        finally:
            log_queue.task_done()

# Start the background thread once
sink_thread = threading.Thread(target=async_sink_worker, daemon=True)
sink_thread.start()

class FocalLoss(nn.Module):
    def __init__(self, alpha=0.8, gamma=2.5):
        super().__init__()
        self.alpha, self.gamma = alpha, gamma

    def forward(self, inputs, targets):
        BCE_loss = F.binary_cross_entropy_with_logits(inputs, targets, reduction='none')
        pt = torch.exp(-BCE_loss)
        return (self.alpha * (1 - pt)**self.gamma * BCE_loss).mean()

class PersistentReactor:
    def __init__(self, feature_df, target_series, config, device):
        self.config = config
        self.device = device
        self.unique_inds = feature_df.columns.tolist()
        
        # Ground Truth Ingestion
        vals = np.nan_to_num(feature_df.values.astype(np.float32))
        self.lake = torch.tensor(vals, device=device)
        self.y_all = torch.tensor(target_series.values.astype(np.float32), device=device).view(1, -1, 1)

        self.num_indicators = len(self.unique_inds)
        self.hidden_dim = config.get("HIDDEN_DIM", 128)
        
        # Resolve Forced Genes (RSI Thesis)
        raw_forced = self.config.get("FORCED_GENES", [])
        resolved_forced_names = set()
        for pattern in raw_forced:
            for ind_name in self.unique_inds:
                if fnmatch.fnmatch(ind_name.lower(), pattern.lower()):
                    resolved_forced_names.add(ind_name)

        # Force unique indices to prevent redundant inputs
        self.forced_indices = list(set([self.unique_inds.index(name) for name in resolved_forced_names]))
        self.num_forced = len(self.forced_indices)
        self.available_pool = [i for i in range(self.num_indicators) if i not in self.forced_indices]

        # Define Population Parameters
        p_size, g_count = config["POP_SIZE"], config["GENE_COUNT"]
        
        # Build Population (Ensuring absolute uniqueness per genome)
        indices_list = []
        for _ in range(p_size):
            free_slots = g_count - self.num_forced
            # Guard against pool exhaustion
            pool = list(set(self.available_pool)) 
            rand_idx = np.random.choice(pool, free_slots, replace=False)
            
            # Cat and Force Unique again as a final fail-safe
            combined = torch.cat([torch.tensor(self.forced_indices), torch.tensor(rand_idx)])
            unique_genome = torch.unique(combined) 
            
            # If unique check dropped a slot, backfill from pool
            while len(unique_genome) < g_count:
                extra = np.random.choice(pool, 1)
                unique_genome = torch.unique(torch.cat([unique_genome, torch.tensor(extra)]))
                
            indices_list.append(unique_genome)

        self.population = torch.stack(indices_list).to(device).long()
        self.thresholds = torch.full((p_size,), 0.7, device=device) 

        # Weights Population (Initialized AFTER p_size/g_count)
        self.pop_W1 = torch.randn(p_size, g_count, self.hidden_dim, device=device) * 0.02
        self.pop_B1 = torch.zeros(p_size, 1, self.hidden_dim, device=device)
        self.pop_W2 = torch.randn(p_size, self.hidden_dim, 1, device=device) * 0.02
        self.pop_B2 = torch.zeros(p_size, 1, 1, device=device)
        
        # Vitality Stats
        self.gene_scores = torch.zeros(self.num_indicators, device=device)
        self.gene_usage = torch.zeros(self.num_indicators, device=device)
        self.decay_factor = 0.95

    def _forward(self, x, w1, b1, w2, b2):
        h1 = F.leaky_relu(torch.bmm(x, w1) + b1, 0.1)
        return torch.bmm(h1, w2) + b2

    def run_generation(self):
        pop_size = self.config["POP_SIZE"]
        chunk_size = self.config["GPU_CHUNK"]
        metrics = {"f1": [], "prec": [], "rec": [], "sigs": []}
        criterion = FocalLoss()
        
        total_len = len(self.lake)
        master_oos_start = int(total_len * 0.9)

        # Apply Regime Decay
        self.gene_scores *= self.decay_factor
        self.gene_usage *= self.decay_factor

        for i in range(0, pop_size, chunk_size):
            end_i = min(i + chunk_size, pop_size)
            curr_chunk = end_i - i
            indices = self.population[i:end_i]

            # Dynamic Training Windows
            window_end = torch.randint(int(total_len * 0.5), master_oos_start, (1,)).item()
            window_start = max(0, window_end - int(total_len * 0.4)) 
            train_split = window_start + int((window_end - window_start) * 0.8)

            x_train = self.lake[window_start:train_split, indices].permute(1, 0, 2)
            y_train = self.y_all[:, window_start:train_split, :].expand(curr_chunk, -1, -1)
            x_val = self.lake[train_split:window_end, indices].permute(1, 0, 2)
            y_val = self.y_all[:, train_split:window_end, :].expand(curr_chunk, -1, -1)

            # Optimization Loop
            w1 = self.pop_W1[i:end_i].detach().requires_grad_(True)
            b1 = self.pop_B1[i:end_i].detach().requires_grad_(True)
            w2 = self.pop_W2[i:end_i].detach().requires_grad_(True)
            b2 = self.pop_B2[i:end_i].detach().requires_grad_(True)
            optimizer = optim.Adam([w1, b1, w2, b2], lr=self.config["LEARNING_RATE"])
            
            for _ in range(self.config["EPOCHS"]):
                optimizer.zero_grad()
                logits = self._forward(x_train, w1, b1, w2, b2)
                loss = criterion(logits, y_train) + (torch.mean(torch.sigmoid(logits)) * 0.5)
                loss.backward()
                torch.nn.utils.clip_grad_norm_([w1, b1, w2, b2], 1.0)
                optimizer.step()

            with torch.no_grad():
                self.pop_W1[i:end_i].copy_(w1)
                self.pop_W2[i:end_i].copy_(w2)

                # Validation Search with Log-Penalty (Sniper Filter)
                val_probs = torch.sigmoid(self._forward(x_val, w1, b1, w2, b2))
                bt, mf1 = torch.full((curr_chunk,), 0.7, device=self.device), torch.zeros(curr_chunk, device=self.device)
                
                # NIT FIX: INCREASED GRID TO 80 POINTS FOR FINER RESOLUTION
                for t in np.linspace(0.6, 0.95, 80):
                    p = (val_probs > t).float()
                    sigs = p.sum(1) + 1e-6
                    tp, fp, fn = (p * y_val).sum(1), (p * (1 - y_val)).sum(1), ((1 - p) * y_val).sum(1)
                    
                    f1 = (2 * tp) / (2 * tp + fp + fn + 1e-6)
                    penalty = torch.log10(sigs.clamp(min=1.0, max=10.0))
                    f1_weighted = f1.view(-1) * penalty.view(-1)
                    
                    mask = f1_weighted > mf1
                    mf1[mask], bt[mask] = f1_weighted[mask], t
                
                self.thresholds[i:end_i].copy_(bt)

                # Final OOS Test
                x_test = self.lake[master_oos_start:, indices].permute(1, 0, 2)
                y_test = self.y_all[:, master_oos_start:, :].expand(curr_chunk, -1, -1)
                test_p = (torch.sigmoid(self._forward(x_test, w1, b1, w2, b2)) > bt.view(-1, 1, 1)).float()

                tp_t = (test_p * y_test).sum(1).view(-1)
                fp_t = (test_p * (1 - y_test)).sum(1).view(-1)
                fn_t = ((1 - test_p) * y_test).sum(1).view(-1)
                f1_s = (2 * tp_t) / (2 * tp_t + fp_t + fn_t + 1e-6)
                
                for idx_c in range(curr_chunk):
                    self.gene_scores[indices[idx_c]] += f1_s[idx_c]
                    self.gene_usage[indices[idx_c]] += 1

                metrics["f1"].append(f1_s.cpu())
                metrics["prec"].append((tp_t / (tp_t + fp_t + 1e-6)).cpu())
                metrics["rec"].append((tp_t / (tp_t + fn_t + 1e-6)).cpu())
                metrics["sigs"].append(test_p.sum(1).view(-1).cpu())
                torch.cuda.empty_cache()

        return {k: torch.cat(v) for k, v in metrics.items()}

    def evolve(self, fitness_scores):
        pop_size = self.config["POP_SIZE"]
        idx = torch.argsort(fitness_scores, descending=True)
        
        # RE-ORDER ALL CUDA TENSORS (Elitism Fix)
        self.population = self.population[idx]
        self.pop_W1, self.pop_W2 = self.pop_W1[idx], self.pop_W2[idx]
        self.pop_B1, self.pop_B2 = self.pop_B1[idx], self.pop_B2[idx]
        self.thresholds = self.thresholds[idx]

        # Stagnation Logic
        fit_mean = torch.mean(fitness_scores)
        fit_std = torch.std(fitness_scores) + 1e-6
        is_stagnant = ((fitness_scores[idx[0]] - fit_mean) / fit_std) < 1.5
        
        keep = max(2, pop_size // 20)
        new_pop, new_w1, new_w2 = self.population.clone(), self.pop_W1.clone(), self.pop_W2.clone()
        vitality = (self.gene_scores + 0.1) / (self.gene_usage + 1.0)
        
        for i in range(keep, pop_size):
            t1, t2 = torch.randint(0, pop_size, (4,)), torch.randint(0, pop_size, (4,))
            p1, p2 = t1[torch.argmax(fitness_scores[idx][t1])], t2[torch.argmax(fitness_scores[idx][t2])]
            
            new_pop[i] = self.population[p1]
            new_w1[i], new_w2[i] = self.pop_W1[p1], self.pop_W2[p1]
            
            # Adaptive Crossover
            if torch.rand(1).item() < (0.85 if is_stagnant else 0.7):
                cut = torch.randint(max(1, self.num_forced), self.config["GENE_COUNT"], (1,)).item()
                head, tail = new_pop[i, :cut], self.population[p2, cut:].clone()
                
                for g in range(len(tail)):
                    if tail[g] in head:
                        # NIT FIX: MULTINOMIAL WITH SOFTMAX FOR PROBABILISTIC BACKFILL
                        found = False
                        v_probs = vitality.softmax(0)
                        candidates = torch.multinomial(v_probs, min(100, len(v_probs)), replacement=False)
                        
                        for cand in candidates:
                            if cand not in head and cand not in tail:
                                tail[g], found = cand, True; break
                        if not found: 
                            tail[g] = torch.tensor(np.random.choice(self.available_pool), device=self.device)
                
                new_pop[i, cut:], new_w1[i, cut:] = tail, self.pop_W1[p2, cut:]

        # Mutation Shock
        mut_rate = self.config["WEIGHT_MUTATION_RATE"] * (3.0 if is_stagnant else 1.0)
        new_w1[keep:] += torch.randn_like(new_w1[keep:]) * mut_rate
        new_w2[keep:] += torch.randn_like(new_w2[keep:]) * mut_rate

        self.population.copy_(new_pop); self.pop_W1.copy_(new_w1); self.pop_W2.copy_(new_w2)
        
        # FINAL GOVERNOR CHECK: Halt on corruption
        for g_idx in range(pop_size):
            if len(torch.unique(self.population[g_idx])) != self.config["GENE_COUNT"]:
                print(f"❌ CRITICAL GENOME CORRUPTION AT POP {g_idx}!")
                import sys; sys.exit(1)