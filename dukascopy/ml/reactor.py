import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
import numpy as np
import pandas as pd

class PersistentReactor:
    """Persistent Reactor implementing evolutionary neural networks for sequence prediction."""

    def __init__(self, feature_df, target_series, config, device):
        """Initializes the reactor with data, population, and architecture.

        Args:
            feature_df (pd.DataFrame): Input features.
            target_series (pd.Series): Target labels.
            config (dict): Configuration dictionary including population size, genes, and hyperparameters.
            device (torch.device): Device to run computations on.
        """
        self.config = config
        self.device = device
        self.dtype = torch.float32
        self.stream = torch.cuda.Stream()
        self.unique_inds = feature_df.columns.tolist()

        # Convert target to float32 tensor and define train/val/test splits
        y_vals = target_series.values.astype(np.float32)
        self.total_len = len(y_vals)
        self.split_val = int(self.total_len * 0.6)
        self.split_test = int(self.total_len * 0.8)

        # Convert features to float32 and normalize
        vals = feature_df.values.astype(np.float32)
        vals = np.nan_to_num(vals, nan=0.0, posinf=0.0, neginf=0.0)
        mu = np.mean(vals[:self.split_val, :], axis=0)
        sigma = np.std(vals[:self.split_val, :], axis=0) + 1e-6
        vals = np.clip((vals - mu) / sigma, -5.0, 5.0)
        self.lake = torch.tensor(vals, device=device, dtype=self.dtype)

        # Prepare target tensors for train/val/test
        y_tensor = torch.tensor(y_vals, device=device, dtype=self.dtype).view(1, -1, 1)
        self.y_train = y_tensor[:, :self.split_val, :]
        self.y_val = y_tensor[:, self.split_val:self.split_test, :]
        self.y_test = y_tensor[:, self.split_test:, :]

        # Compute class balancing weight
        pos_count = (self.y_train > 0.5).sum().item()
        neg_count = (self.y_train < 0.5).sum().item()
        self.pos_weight = torch.tensor([neg_count / (pos_count + 1e-6)], device=device)

        # Network architecture
        self.num_indicators = len(self.unique_inds)
        self.hidden_dim = 128

        # Initialize population weights and biases
        self.pop_W1 = torch.randn(config["POP_SIZE"], config["GENE_COUNT"], self.hidden_dim, device=device) * 0.02
        self.pop_B1 = torch.zeros(config["POP_SIZE"], 1, self.hidden_dim, device=device)
        self.pop_W2 = torch.randn(config["POP_SIZE"], self.hidden_dim, 1, device=device) * 0.02
        self.pop_B2 = torch.zeros(config["POP_SIZE"], 1, 1, device=device)

        # Initialize genetic population (feature indices) and thresholds
        indices = [torch.randperm(self.num_indicators)[:config["GENE_COUNT"]] for _ in range(config["POP_SIZE"])]
        self.population = torch.stack(indices).to(device)
        self.thresholds = torch.full((config["POP_SIZE"],), 0.5, device=device)

    def _forward(self, x, w1, b1, w2, b2):
        """Performs forward pass of a mini-network.

        Args:
            x (torch.Tensor): Input tensor of shape (batch, seq_len, features).
            w1 (torch.Tensor): First layer weights.
            b1 (torch.Tensor): First layer biases.
            w2 (torch.Tensor): Second layer weights.
            b2 (torch.Tensor): Second layer biases.

        Returns:
            torch.Tensor: Output logits of shape (batch, seq_len, 1).
        """
        h1 = F.leaky_relu(torch.bmm(x, w1) + b1, 0.1)  # First hidden layer with LeakyReLU
        return torch.bmm(h1, w2) + b2  # Output layer

    def run_generation(self):
        """Runs one generation of training for all networks in the population.

        Uses GPU chunking, validation-based early stopping, and updates thresholds.

        Returns:
            dict: Dictionary of evaluation metrics containing 'f1', 'prec', 'rec', 'sigs'.
        """
        pop_size = self.config["POP_SIZE"]
        chunk_size = self.config["GPU_CHUNK"]
        metrics = {"f1": [], "prec": [], "rec": [], "sigs": []}

        for i in range(0, pop_size, chunk_size):
            end_i = min(i + chunk_size, pop_size)
            actual_chunk_size = end_i - i

            # Select features for this chunk
            indices = self.population[i:end_i]
            x_train = self.lake[:self.split_val, indices].permute(1, 0, 2)
            y_train = self.y_train.expand(actual_chunk_size, -1, -1)

            x_val = self.lake[self.split_val:self.split_test, indices].permute(1, 0, 2)
            y_val = self.y_val.expand(actual_chunk_size, -1, -1)

            # Initialize weights for gradient descent
            w1 = self.pop_W1[i:end_i].detach().requires_grad_(True)
            b1 = self.pop_B1[i:end_i].detach().requires_grad_(True)
            w2 = self.pop_W2[i:end_i].detach().requires_grad_(True)
            b2 = self.pop_B2[i:end_i].detach().requires_grad_(True)

            optimizer = optim.Adam([w1, b1, w2, b2], lr=self.config["LEARNING_RATE"])
            scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', factor=0.5, patience=3)
            criterion = nn.BCEWithLogitsLoss(pos_weight=self.pos_weight)

            best_val_loss = float('inf')
            patience_counter = 0

            # Training loop with early stopping
            for epoch in range(self.config["EPOCHS"]):
                optimizer.zero_grad()
                logits_train = self._forward(x_train, w1, b1, w2, b2)
                loss_train = criterion(logits_train, y_train)
                loss_train.backward()
                torch.nn.utils.clip_grad_norm_([w1, b1, w2, b2], 1.0)
                optimizer.step()

                with torch.no_grad():
                    logits_val = self._forward(x_val, w1, b1, w2, b2)
                    loss_val = criterion(logits_val, y_val).item()

                scheduler.step(loss_val)

                # Early stopping check
                if loss_val < best_val_loss - 1e-4:
                    best_val_loss = loss_val
                    patience_counter = 0
                else:
                    patience_counter += 1

                if patience_counter >= 7:
                    break

            # Update population with trained weights
            with torch.no_grad():
                self.pop_W1[i:end_i].copy_(w1)
                self.pop_B1[i:end_i].copy_(b1)
                self.pop_W2[i:end_i].copy_(w2)
                self.pop_B2[i:end_i].copy_(b2)

                # Determine best threshold for validation set
                val_probs = torch.sigmoid(self._forward(x_val, w1, b1, w2, b2))
                best_t = torch.full((actual_chunk_size,), 0.5, device=self.device)
                max_f1_val = torch.zeros(actual_chunk_size, device=self.device)

                for t in np.linspace(0.01, 0.99, 50):
                    p = (val_probs > t).float()
                    tp = (p * y_val).sum(1)
                    fp = (p * (1 - y_val)).sum(1)
                    fn = ((1 - p) * y_val).sum(1)
                    f1 = (2 * tp) / (2 * tp + fp + fn + 1e-6)
                    mask = f1.view(-1) > max_f1_val
                    max_f1_val[mask], best_t[mask] = f1.view(-1)[mask], t

                self.thresholds[i:end_i].copy_(best_t)

                # Evaluate test set metrics
                x_test = self.lake[self.split_test:, indices].permute(1, 0, 2)
                y_test = self.y_test.expand(actual_chunk_size, -1, -1)
                test_probs = torch.sigmoid(self._forward(x_test, w1, b1, w2, b2))
                final_p = (test_probs > best_t.view(-1, 1, 1)).float()

                tp_t = (final_p * y_test).sum(1).view(-1)
                fp_t = (final_p * (1 - y_test)).sum(1).view(-1)
                fn_t = ((1 - final_p) * y_test).sum(1).view(-1)

                metrics["f1"].append((2 * tp_t) / (2 * tp_t + fp_t + fn_t + 1e-6))
                metrics["prec"].append(tp_t / (tp_t + fp_t + 1e-6))
                metrics["rec"].append(tp_t / (tp_t + fn_t + 1e-6))
                metrics["sigs"].append(final_p.sum(1).view(-1))

        return {k: torch.cat(v) for k, v in metrics.items()}

    def evolve(self, fitness_scores):
        """Performs evolutionary step: selection, crossover, and mutation.

        Args:
            fitness_scores (torch.Tensor): Fitness scores for the current population.
        """
        pop_size = self.config["POP_SIZE"]
        idx = torch.argsort(fitness_scores, descending=True)
        keep = max(2, pop_size // 10)
        elites_idx = idx[:keep]

        # Crossover for the remaining population
        for i in range(keep, pop_size):
            p1, p2 = elites_idx[torch.randint(0, keep, (2,))]
            self.population[i] = self.population[p1]
            self.pop_W1[i] = self.pop_W1[p1]
            self.pop_W2[i] = self.pop_W2[p1]

            if torch.rand(1).item() < 0.5:
                cut = torch.randint(1, self.config["GENE_COUNT"], (1,)).item()
                self.population[i, cut:] = self.population[p2, cut:]
                self.pop_W1[i, cut:] = self.pop_W1[p2, cut:]

        # Mutation
        rate = self.config["WEIGHT_MUTATION_RATE"]
        for i in range(keep, pop_size):
            self.pop_W1[i] += torch.randn_like(self.pop_W1[i]) * rate
            self.pop_W2[i] += torch.randn_like(self.pop_W2[i]) * rate

            if torch.rand(1).item() < 0.3:
                mut_idx = torch.randint(0, self.config["GENE_COUNT"], (1,))
                self.population[i, mut_idx] = torch.randint(0, self.num_indicators, (1,))
