import torch
import torch.nn.functional as F
import numpy as np
import time


class PersistentReactor:
    """Population-based neural reactor with evolutionary feature selection.

    This class maintains a population of small neural networks, each operating
    on a selected subset of input indicators ("genes"). Networks are trained
    via gradient descent and evolved via selection and mutation based on
    performance metrics (F1 score).

    Attributes:
        config (dict): Configuration dictionary controlling population size,
            learning rate, mutation rate, epochs, etc.
        device (torch.device): CUDA or CPU device.
        dtype (torch.dtype): Floating point precision used throughout.
        stream (torch.cuda.Stream): Dedicated CUDA stream for async execution.
        lake (torch.Tensor): Normalized full feature matrix [T, F].
        population (torch.Tensor): Feature indices for each genome
            [POP_SIZE, GENE_COUNT].
        thresholds (torch.Tensor): Per-genome decision thresholds.
    """

    def __init__(self, feature_df, target_series, config, device):
        """Initializes data, population, and model parameters.

        Args:
            feature_df (pd.DataFrame): Input feature dataframe [T, F].
            target_series (pd.Series): Binary target series [T].
            config (dict): Hyperparameter and evolution configuration.
            device (torch.device): Device on which all tensors are allocated.
        """
        self.config = config
        self.device = device
        self.dtype = torch.float32

        # Dedicated CUDA stream to overlap compute and memory operations
        self.stream = torch.cuda.Stream()

        # Positive class weighting to counter heavy class imbalance
        self.pos_weight = torch.tensor(200.0, device=device)

        # Convert feature dataframe to float32 numpy array
        vals = feature_df.values.astype(np.float32)

        # Replace NaNs and infinities with zeros
        vals = np.nan_to_num(vals, nan=0.0, posinf=0.0, neginf=0.0)

        # Train / test split index
        self.split = int(len(vals) * 0.8)

        # Compute normalization statistics on training subset only
        train_subset = vals[:self.split, :]
        mu = np.mean(train_subset, axis=0)
        sigma = np.std(train_subset, axis=0)

        # Z-score normalization with numerical stability
        vals = (vals - mu) / (sigma + 1e-6)

        # Clip extreme values to stabilize training
        vals = np.clip(vals, -5.0, 5.0)

        # Final NaN cleanup after normalization
        vals = np.nan_to_num(vals, nan=0.0)

        # Store normalized features as a GPU tensor
        self.lake = torch.tensor(vals, device=device, dtype=self.dtype)

        # Metadata for feature indexing
        self.col_names = list(feature_df.columns)
        self.unique_inds = self.col_names
        self.num_indicators = len(self.unique_inds)

        # Prepare target tensor [1, T, 1] for broadcasting
        y_raw = (
            torch.tensor(target_series.values, device=device)
            .float()
            .view(1, -1, 1)
        )

        # Split targets into train and test
        self.y_train = y_raw[:, :self.split, :]
        self.y_test = y_raw[:, self.split:, :]

        # Hidden layer width for all population members
        hidden = 128

        # Population weights and biases
        self.pop_W1 = (
            torch.randn(
                config["POP_SIZE"],
                config["GENE_COUNT"],
                hidden,
                device=device,
            )
            * 0.01
        )
        self.pop_W2 = (
            torch.randn(
                config["POP_SIZE"],
                hidden,
                1,
                device=device,
            )
            * 0.01
        )
        self.pop_B1 = torch.zeros(
            config["POP_SIZE"], 1, hidden, device=device
        )
        self.pop_B2 = torch.full(
            (config["POP_SIZE"], 1, 1), -0.5, device=device
        )

        # Randomly initialize feature subsets (genes) per genome
        pop_indices = []
        for _ in range(config["POP_SIZE"]):
            pop_indices.append(
                torch.randperm(self.num_indicators)[
                    : config["GENE_COUNT"]
                ]
            )
        self.population = torch.stack(pop_indices).to(device)

        # Initial classification thresholds per genome
        self.thresholds = torch.full(
            (config["POP_SIZE"],),
            0.1,
            device=device,
            dtype=self.dtype,
        )

    def run_generation(self, do_profile=False):
        """Runs one full training + evaluation generation.

        Each genome is trained on its selected feature subset using
        manual backpropagation. Performance metrics are computed on
        the held-out test set.

        Args:
            do_profile (bool): If True, prints GPU memory usage per chunk.

        Returns:
            dict[str, torch.Tensor]: Flattened tensors of metrics:
                - 'f1': F1 score per genome
                - 'prec': precision per genome
                - 'rec': recall per genome
                - 'sigs': number of positive signals per genome
        """
        metrics = {"f1": [], "prec": [], "rec": [], "sigs": []}
        lr = self.config["LEARNING_RATE"]

        # Split population into GPU-friendly chunks
        col_chunks = torch.split(
            self.population, self.config["GPU_CHUNK"]
        )
        n_chunks = len(col_chunks)

        # Execute training asynchronously on a dedicated CUDA stream
        with torch.cuda.stream(self.stream):
            for idx, chunk_cols in enumerate(col_chunks):
                if do_profile:
                    vram = (
                        torch.cuda.memory_allocated(self.device)
                        / 1024**3
                    )
                    print(
                        f"  ⚡ [Chunk {idx+1:02d}/{n_chunks}] "
                        f"VRAM: {vram:.2f}GB",
                        end="\r",
                    )

                # Determine population slice indices
                start_i = idx * self.config["GPU_CHUNK"]
                p_size = chunk_cols.size(0)

                # Clone weights for isolated training
                W1 = (
                    self.pop_W1[start_i : start_i + p_size]
                    .detach()
                    .clone()
                )
                W2 = (
                    self.pop_W2[start_i : start_i + p_size]
                    .detach()
                    .clone()
                )
                B1 = (
                    self.pop_B1[start_i : start_i + p_size]
                    .detach()
                    .clone()
                )
                B2 = (
                    self.pop_B2[start_i : start_i + p_size]
                    .detach()
                    .clone()
                )

                # Gather feature subsets and align dimensions
                X_batch = self.lake[: self.split, chunk_cols].permute(
                    1, 0, 2
                )
                Y_batch = self.y_train.expand(p_size, -1, -1)

                # Gradient descent loop
                for epoch in range(self.config["EPOCHS"]):
                    # Forward pass: hidden layer
                    Z1 = torch.bmm(X_batch, W1) + B1
                    H1 = F.leaky_relu(Z1, 0.1)

                    # Output logits with clamping for numerical stability
                    logits = torch.bmm(H1, W2) + B2
                    logits = torch.clamp(logits, -15.0, 15.0)

                    # Abort on numerical failure
                    if torch.isnan(logits).any():
                        W1.fill_(0.0)
                        W2.fill_(0.0)
                        break

                    # Sigmoid predictions
                    pred = torch.sigmoid(logits)

                    # Output gradient with class reweighting
                    d_out = pred - Y_batch
                    d_out = torch.where(
                        Y_batch > 0.5,
                        d_out * self.pos_weight,
                        d_out,
                    )

                    # Gradient norm clipping
                    gnorm = torch.norm(
                        d_out, dim=(1, 2), keepdim=True
                    )
                    d_out = torch.where(
                        gnorm > 1.0,
                        d_out / (gnorm + 1e-6),
                        d_out,
                    )

                    # Backprop into output layer
                    W2.sub_(
                        torch.bmm(H1.transpose(1, 2), d_out)
                        * lr
                    )
                    B2.sub_(
                        d_out.sum(dim=1, keepdim=True) * lr
                    )

                    # Backprop into hidden layer
                    d_h1 = torch.bmm(
                        d_out, W2.transpose(1, 2)
                    ) * torch.where(Z1 > 0, 1.0, 0.1)

                    W1.sub_(
                        torch.bmm(
                            X_batch.transpose(1, 2), d_h1
                        )
                        * lr
                    )
                    B1.sub_(
                        d_h1.sum(dim=1, keepdim=True) * lr
                    )

                # Write trained parameters back to population
                self.pop_W1[start_i : start_i + p_size].copy_(W1)
                self.pop_W2[start_i : start_i + p_size].copy_(W2)
                self.pop_B1[start_i : start_i + p_size].copy_(B1)
                self.pop_B2[start_i : start_i + p_size].copy_(B2)

                # Evaluation phase (no gradients)
                with torch.no_grad():
                    X_test = self.lake[
                        self.split :, chunk_cols
                    ].permute(1, 0, 2)

                    logits_test = (
                        torch.bmm(
                            F.leaky_relu(
                                torch.bmm(X_test, W1) + B1,
                                0.1,
                            ),
                            W2,
                        )
                        + B2
                    )

                    preds = (
                        torch.sigmoid(logits_test)
                        > self.thresholds[
                            start_i : start_i + p_size
                        ].view(-1, 1, 1)
                    ).float()

                    Y_test = self.y_test.expand(p_size, -1, -1)

                    # Confusion matrix components
                    tp = (preds * Y_test).sum(1)
                    fp = (preds * (1 - Y_test)).sum(1)
                    fn = ((1 - preds) * Y_test).sum(1)

                    # Metrics
                    metrics["f1"].append(
                        (2 * tp)
                        / (2 * tp + fp + fn + 1e-6)
                    )
                    metrics["prec"].append(
                        tp / (tp + fp + 1e-6)
                    )
                    metrics["rec"].append(
                        tp / (tp + fn + 1e-6)
                    )
                    metrics["sigs"].append(preds.sum(1))

        # Synchronize default stream with custom stream
        torch.cuda.current_stream().wait_stream(self.stream)

        # Concatenate chunked metrics
        return {
            k: torch.cat(v).view(-1) for k, v in metrics.items()
        }

    def evolve(self, f1_scores):
        """Evolves the population based on F1 fitness.

        Top-performing genomes are retained and replicated. Weights,
        thresholds, and feature selections are mutated to introduce
        variation.

        Args:
            f1_scores (torch.Tensor): F1 score per genome [POP_SIZE].
        """
        pop_size = self.config["POP_SIZE"]

        # Rank genomes by fitness
        idx = torch.argsort(f1_scores, descending=True)

        # Elitism: keep top 10%
        keep = pop_size // 10

        # Repeat elites to refill population
        repeats = idx[:keep].repeat(
            (pop_size // keep) + 1
        )[:pop_size]

        # Copy elite genomes
        self.population.copy_(self.population[repeats])
        self.thresholds.copy_(self.thresholds[repeats])

        # Mutate thresholds
        self.thresholds.add_(
            torch.randn_like(self.thresholds) * 0.01
        )
        self.thresholds.clamp_(0.01, 0.99)

        # Mutate weights and biases
        rate = self.config["WEIGHT_MUTATION_RATE"]
        for name, p in [
            ("W1", self.pop_W1),
            ("W2", self.pop_W2),
            ("B1", self.pop_B1),
            ("B2", self.pop_B2),
        ]:
            mutation_scale = (
                rate * 0.1 if "B" in name else rate
            )
            p.copy_(
                p[repeats]
                + torch.randn_like(p) * mutation_scale
            )

        # Feature (gene) mutation for non-elites
        for i in range(keep, pop_size):
            mut_mask = (
                torch.rand(
                    self.config["GENE_COUNT"],
                    device=self.device,
                )
                < 0.1
            )
            if mut_mask.any():
                current_genes = self.population[i].tolist()

                # Candidate features not currently selected
                available_pool = np.setdiff1d(
                    np.arange(self.num_indicators),
                    current_genes,
                )

                if len(available_pool) > 0:
                    num_to_replace = mut_mask.sum().item()
                    new_picks = np.random.choice(
                        available_pool,
                        min(
                            len(available_pool),
                            int(num_to_replace),
                        ),
                        replace=False,
                    )
                    mut_indices = torch.where(mut_mask)[0]
                    for m_idx, g_val in zip(
                        mut_indices, new_picks
                    ):
                        self.population[i, m_idx] = int(
                            g_val
                        )
