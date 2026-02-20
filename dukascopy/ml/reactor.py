import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
import numpy as np
import threading
import queue
import time
import os

# Version 5.0 - Persistent Reactor: Specialized Directional Evolution
# Targets: Bottom-Only or Top-Only optimization via filtered Ingestion

log_queue = queue.Queue(maxsize=100) 

# Ensure checkpoint directory exists for the Async Sink
if not os.path.exists('checkpoints'):
    os.makedirs('checkpoints')
if not os.path.exists('logs'):
    os.makedirs('logs')

def async_sink_worker():
    """Consumes metrics and model states to free up the Main Thread."""
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

sink_thread = threading.Thread(target=async_sink_worker, daemon=True)
sink_thread.start()

class FocalLoss(nn.Module):
    def __init__(self, alpha=0.8, gamma=2.5):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma

    def forward(self, inputs, targets):
        BCE_loss = F.binary_cross_entropy_with_logits(inputs, targets, reduction='none')
        pt = torch.exp(-BCE_loss)
        return (self.alpha * (1 - pt)**self.gamma * BCE_loss).mean()

class PersistentReactor:
    def __init__(self, feature_df, target_series, config, device):
        self.config = config
        self.device = device
        self.unique_inds = feature_df.columns.tolist()

        # Pre-process Lake (Z-scoring handled at ingest or here)
        vals = np.nan_to_num(feature_df.values.astype(np.float32))
        self.lake = torch.tensor(vals, device=device)
        self.y_all = torch.tensor(target_series.values.astype(np.float32), device=device).view(1, -1, 1)

        self.num_indicators = len(self.unique_inds)
        self.hidden_dim = 128

        # GPU Populations
        self.pop_W1 = torch.randn(config["POP_SIZE"], config["GENE_COUNT"], self.hidden_dim, device=device) * 0.02
        self.pop_B1 = torch.zeros(config["POP_SIZE"], 1, self.hidden_dim, device=device)
        self.pop_W2 = torch.randn(config["POP_SIZE"], self.hidden_dim, 1, device=device) * 0.02
        self.pop_B2 = torch.zeros(config["POP_SIZE"], 1, 1, device=device)

        indices = [torch.randperm(self.num_indicators)[:config["GENE_COUNT"]] for _ in range(config["POP_SIZE"])]
        self.population = torch.stack(indices).to(device)
        self.thresholds = torch.full((config["POP_SIZE"],), 0.7, device=device) 
        
        # Vitality Stats
        self.gene_scores = torch.zeros(self.num_indicators, device=device)
        self.gene_usage = torch.zeros(self.num_indicators, device=device)

    def _forward(self, x, w1, b1, w2, b2):
        h1 = F.leaky_relu(torch.bmm(x, w1) + b1, 0.1)
        return torch.bmm(h1, w2) + b2

    def run_generation(self):
        """
        V5.0: DIRECTIONAL SPECIALIST ENGINE
        Uses Rolling Walk-Forward with Master OOS Holdout.
        """
        pop_size = self.config["POP_SIZE"]
        chunk_size = self.config["GPU_CHUNK"]
        metrics = {"f1": [], "prec": [], "rec": [], "sigs": []}
        criterion = FocalLoss()
        
        total_len = len(self.lake)
        master_oos_start = int(total_len * 0.9) # Strict 10% holdout

        for i in range(0, pop_size, chunk_size):
            end_i = min(i + chunk_size, pop_size)
            curr_chunk = end_i - i
            indices = self.population[i:end_i]

            # Randomized training windows to prevent overfitting to specific cycles
            window_end = torch.randint(int(total_len * 0.5), master_oos_start, (1,)).item()
            window_start = max(0, window_end - int(total_len * 0.4)) 
            train_split = window_start + int((window_end - window_start) * 0.8)

            # Parallel Slicing for CUDA Chunk
            x_train = self.lake[window_start:train_split, indices].permute(1, 0, 2)
            y_train = self.y_all[:, window_start:train_split, :].expand(curr_chunk, -1, -1)
            x_val = self.lake[train_split:window_end, indices].permute(1, 0, 2)
            y_val = self.y_all[:, train_split:window_end, :].expand(curr_chunk, -1, -1)

            # Optimizer Path (Adam on GPU)
            w1 = self.pop_W1[i:end_i].detach().requires_grad_(True)
            b1 = self.pop_B1[i:end_i].detach().requires_grad_(True)
            w2 = self.pop_W2[i:end_i].detach().requires_grad_(True)
            b2 = self.pop_B2[i:end_i].detach().requires_grad_(True)
            optimizer = optim.Adam([w1, b1, w2, b2], lr=self.config["LEARNING_RATE"])
            
            for _ in range(self.config["EPOCHS"]):
                optimizer.zero_grad()
                logits = self._forward(x_train, w1, b1, w2, b2)
                # Sparsity constraint + Focal Loss
                loss = criterion(logits, y_train) + (torch.mean(torch.sigmoid(logits)) * 0.5)
                loss.backward()
                torch.nn.utils.clip_grad_norm_([w1, b1, w2, b2], 1.0)
                optimizer.step()

            with torch.no_grad():
                self.pop_W1[i:end_i].copy_(w1)
                self.pop_W2[i:end_i].copy_(w2)

                # Dynamic Threshold Tuning (Searching for the 1.00 Precision sweet spot)
                val_probs = torch.sigmoid(self._forward(x_val, w1, b1, w2, b2))
                bt, mf1 = torch.full((curr_chunk,), 0.7, device=self.device), torch.zeros(curr_chunk, device=self.device)
                
                for t in np.linspace(0.6, 0.95, 30):
                    p = (val_probs > t).float()
                    tp = (p * y_val).sum(1)
                    fp = (p * (1 - y_val)).sum(1)
                    fn = ((1 - p) * y_val).sum(1)
                    f1 = (2 * tp) / (2 * tp + fp + fn + 1e-6)
                    mask = f1.view(-1) > mf1
                    mf1[mask], bt[mask] = f1.view(-1)[mask], t
                
                self.thresholds[i:end_i].copy_(bt)

                # Evaluation on Master OOS
                x_test = self.lake[master_oos_start:, indices].permute(1, 0, 2)
                y_test = self.y_all[:, master_oos_start:, :].expand(curr_chunk, -1, -1)
                test_logits = self._forward(x_test, w1, b1, w2, b2)
                test_p = (torch.sigmoid(test_logits) > bt.view(-1, 1, 1)).float()

                tp_t = (test_p * y_test).sum(1).view(-1)
                fp_t = (test_p * (1 - y_test)).sum(1).view(-1)
                fn_t = ((1 - test_p) * y_test).sum(1).view(-1)

                f1_s = (2 * tp_t) / (2 * tp_t + fp_t + fn_t + 1e-6)
                
                # Update Vitality Metrics for genetic survival
                for idx_c in range(curr_chunk):
                    self.gene_scores[indices[idx_c]] += f1_s[idx_c]
                    self.gene_usage[indices[idx_c]] += 1

                # Async Ship to CPU
                metrics["f1"].append(f1_s.cpu())
                metrics["prec"].append((tp_t / (tp_t + fp_t + 1e-6)).cpu())
                metrics["rec"].append((tp_t / (tp_t + fn_t + 1e-6)).cpu())
                metrics["sigs"].append(test_p.sum(1).view(-1).cpu())

                # Explicit VRAM Cleaning
                del x_train, y_train, x_val, y_val, x_test, y_test, val_probs, test_logits, test_p
                torch.cuda.empty_cache()

        return {k: torch.cat(v) for k, v in metrics.items()}

    def evolve(self, fitness_scores):
        pop_size = self.config["POP_SIZE"]
        idx = torch.argsort(fitness_scores, descending=True)
        keep = max(2, pop_size // 20)
        
        new_pop, new_w1, new_w2 = self.population.clone(), self.pop_W1.clone(), self.pop_W2.clone()

        # Elitism & Tournament Selection
        for i in range(keep, pop_size):
            t1, t2 = torch.randint(0, pop_size, (4,)), torch.randint(0, pop_size, (4,))
            p1, p2 = t1[torch.argmax(fitness_scores[t1])], t2[torch.argmax(fitness_scores[t2])]
            
            new_pop[i] = self.population[p1]
            new_w1[i], new_w2[i] = self.pop_W1[p1], self.pop_W2[p1]
            
            if torch.rand(1).item() < 0.6: # Structural Crossover
                cut = torch.randint(1, self.config["GENE_COUNT"], (1,)).item()
                head, tail = new_pop[i, :cut], self.population[p2, cut:].clone()
                for g in range(len(tail)):
                    if tail[g] in head: tail[g] = torch.randint(0, self.num_indicators, (1,))
                new_pop[i, cut:] = tail
                new_w1[i, cut:] = self.pop_W1[p2, cut:]

        # Vitality-weighted Mutation
        vitality = (self.gene_scores + 0.1) / (self.gene_usage + 1.0)
        for i in range(keep, pop_size):
            new_w1[i] += torch.randn_like(new_w1[i]) * self.config["WEIGHT_MUTATION_RATE"]
            new_w2[i] += torch.randn_like(new_w2[i]) * self.config["WEIGHT_MUTATION_RATE"]
            if torch.rand(1).item() < 0.3:
                m_idx = torch.randint(0, self.config["GENE_COUNT"], (1,))
                candidate = torch.multinomial(vitality, 1)
                if candidate not in new_pop[i]: 
                    new_pop[i][m_idx] = candidate

        self.population.copy_(new_pop)
        self.pop_W1.copy_(new_w1)
        self.pop_W2.copy_(new_w2)