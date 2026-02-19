import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
import numpy as np

class FocalLoss(nn.Module):
    def __init__(self, alpha=0.2, gamma=2.5): # Increased gamma for harder focus
        super(FocalLoss, self).__init__()
        self.alpha = alpha
        self.gamma = gamma

    def forward(self, inputs, targets):
        BCE_loss = F.binary_cross_entropy_with_logits(inputs, targets, reduction='none')
        pt = torch.exp(-BCE_loss)
        F_loss = self.alpha * (1 - pt)**self.gamma * BCE_loss
        return F_loss.mean()

class PersistentReactor:
    def __init__(self, feature_df, target_series, config, device):
        self.config = config
        self.device = device
        self.dtype = torch.float32
        self.unique_inds = feature_df.columns.tolist()

        y_vals = target_series.values.astype(np.float32)
        self.total_len = len(y_vals)
        self.split_val = int(self.total_len * 0.6)
        self.split_test = int(self.total_len * 0.8)

        # Pre-processing
        vals = feature_df.values.astype(np.float32)
        vals = np.nan_to_num(vals, nan=0.0, posinf=0.0, neginf=0.0)
        mu = np.mean(vals[:self.split_val, :], axis=0)
        sigma = np.std(vals[:self.split_val, :], axis=0) + 1e-6
        vals = np.clip((vals - mu) / sigma, -5.0, 5.0)
        self.lake = torch.tensor(vals, device=device, dtype=self.dtype)

        self.y_train = torch.tensor(y_vals[:self.split_val], device=device).view(1, -1, 1)
        self.y_val = torch.tensor(y_vals[self.split_val:self.split_test], device=device).view(1, -1, 1)
        self.y_test = torch.tensor(y_vals[self.split_test:], device=device).view(1, -1, 1)

        self.num_indicators = len(self.unique_inds)
        self.hidden_dim = 128

        # Population Tensors
        self.pop_W1 = torch.randn(config["POP_SIZE"], config["GENE_COUNT"], self.hidden_dim, device=device) * 0.02
        self.pop_B1 = torch.zeros(config["POP_SIZE"], 1, self.hidden_dim, device=device)
        self.pop_W2 = torch.randn(config["POP_SIZE"], self.hidden_dim, 1, device=device) * 0.02
        self.pop_B2 = torch.zeros(config["POP_SIZE"], 1, 1, device=device)

        indices = [torch.randperm(self.num_indicators)[:config["GENE_COUNT"]] for _ in range(config["POP_SIZE"])]
        self.population = torch.stack(indices).to(device)
        self.thresholds = torch.full((config["POP_SIZE"],), 0.5, device=device)
        
        # Track "Gene Performance" to Prune Noise
        self.gene_history = torch.zeros(self.num_indicators, device=device)

    def _forward(self, x, w1, b1, w2, b2):
        h1 = F.leaky_relu(torch.bmm(x, w1) + b1, 0.1)
        return torch.bmm(h1, w2) + b2

    def run_generation(self):
        pop_size = self.config["POP_SIZE"]
        chunk_size = self.config["GPU_CHUNK"]
        metrics = {"f1": [], "prec": [], "rec": [], "sigs": []}
        criterion = FocalLoss()

        for i in range(0, pop_size, chunk_size):
            end_i = min(i + chunk_size, pop_size)
            actual_chunk_size = end_i - i

            indices = self.population[i:end_i]
            x_train = self.lake[:self.split_val, indices].permute(1, 0, 2)
            y_train = self.y_train.expand(actual_chunk_size, -1, -1)
            x_val = self.lake[self.split_val:self.split_test, indices].permute(1, 0, 2)
            y_val = self.y_val.expand(actual_chunk_size, -1, -1)

            w1 = self.pop_W1[i:end_i].detach().requires_grad_(True)
            b1 = self.pop_B1[i:end_i].detach().requires_grad_(True)
            w2 = self.pop_W2[i:end_i].detach().requires_grad_(True)
            b2 = self.pop_B2[i:end_i].detach().requires_grad_(True)

            optimizer = optim.Adam([w1, b1, w2, b2], lr=self.config["LEARNING_RATE"])
            scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', factor=0.5, patience=3)

            best_v_loss = float('inf')
            patience = 0
            for epoch in range(self.config["EPOCHS"]):
                optimizer.zero_grad()
                loss = criterion(self._forward(x_train, w1, b1, w2, b2), y_train)
                loss.backward()
                torch.nn.utils.clip_grad_norm_([w1, b1, w2, b2], 1.0)
                optimizer.step()

                with torch.no_grad():
                    v_loss = criterion(self._forward(x_val, w1, b1, w2, b2), y_val).item()
                scheduler.step(v_loss)
                if v_loss < best_v_loss - 1e-4:
                    best_v_loss, patience = v_loss, 0
                else:
                    patience += 1
                if patience >= 5: break

            with torch.no_grad():
                self.pop_W1[i:end_i].copy_(w1)
                self.pop_B1[i:end_i].copy_(b1)
                self.pop_W2[i:end_i].copy_(w2)
                self.pop_B2[i:end_i].copy_(b2)

                # Threshold Search
                val_probs = torch.sigmoid(self._forward(x_val, w1, b1, w2, b2))
                bt = torch.full((actual_chunk_size,), 0.5, device=self.device)
                mf1 = torch.zeros(actual_chunk_size, device=self.device)

                for t in np.linspace(0.1, 0.95, 80): # Avoid extreme edges
                    p = (val_probs > t).float()
                    tp = (p * y_val).sum(1)
                    fp = (p * (1 - y_val)).sum(1)
                    fn = ((1 - p) * y_val).sum(1)
                    f1 = (2 * tp) / (2 * tp + fp + fn + 1e-6)
                    mask = f1.view(-1) > mf1
                    mf1[mask], bt[mask] = f1.view(-1)[mask], t

                self.thresholds[i:end_i].copy_(bt)
                
                # Evaluation
                x_test = self.lake[self.split_test:, indices].permute(1, 0, 2)
                y_test = self.y_test.expand(actual_chunk_size, -1, -1)
                test_p = torch.sigmoid(self._forward(x_test, w1, b1, w2, b2))
                fin_p = (test_p > bt.view(-1, 1, 1)).float()

                tp_t = (fin_p * y_test).sum(1).view(-1)
                fp_t = (fin_p * (1 - y_test)).sum(1).view(-1)
                fn_t = ((1 - fin_p) * y_test).sum(1).view(-1)

                f1_scores = (2 * tp_t) / (2 * tp_t + fp_t + fn_t + 1e-6)
                metrics["f1"].append(f1_scores)
                metrics["prec"].append(tp_t / (tp_t + fp_t + 1e-6))
                metrics["rec"].append(tp_t / (tp_t + fn_t + 1e-6))
                metrics["sigs"].append(fin_p.sum(1).view(-1))
                
                # Update gene history (global indicator score)
                for batch_idx in range(actual_chunk_size):
                    self.gene_history[indices[batch_idx]] += f1_scores[batch_idx]

        return {k: torch.cat(v) for k, v in metrics.items()}

    def evolve(self, fitness_scores):
        pop_size = self.config["POP_SIZE"]
        idx = torch.argsort(fitness_scores, descending=True)
        keep = max(4, pop_size // 10)
        elites_idx = idx[:keep]

        # Diversified Selection: Choose parents that aren't too similar
        for i in range(keep, pop_size):
            p1 = elites_idx[torch.randint(0, keep // 2, (1,))] # Top 5% parent
            p2 = elites_idx[torch.randint(keep // 2, keep, (1,))] # Mid-elite parent
            
            self.population[i] = self.population[p1]
            self.pop_W1[i], self.pop_W2[i] = self.pop_W1[p1], self.pop_W2[p1]
            
            if torch.rand(1).item() < 0.6: # Crossover
                cut = torch.randint(1, self.config["GENE_COUNT"], (1,)).item()
                self.population[i, cut:] = self.population[p2, cut:]
                self.pop_W1[i, cut:] = self.pop_W1[p2, cut:]

        # Forced Gene Exploration
        rate = self.config["WEIGHT_MUTATION_RATE"]
        for i in range(keep, pop_size):
            self.pop_W1[i] += torch.randn_like(self.pop_W1[i]) * rate
            self.pop_W2[i] += torch.randn_like(self.pop_W2[i]) * rate
            
            # If gene is underperforming globally, swap it out
            if torch.rand(1).item() < 0.3:
                mut_idx = torch.randint(0, self.config["GENE_COUNT"], (1,))
                # Weighted random selection favoring indicators with higher historical f1
                weights = self.gene_history + 0.1
                new_gene = torch.multinomial(weights, 1)
                self.population[i, mut_idx] = new_gene