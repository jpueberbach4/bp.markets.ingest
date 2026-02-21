"""
=============================================================================
Quantitative Discovery Engine (Reactor)
=============================================================================

This module implements a hybrid Machine Learning architecture combining 
Neural Networks (via PyTorch) and a Genetic Algorithm (GA). It is specifically 
designed for "Bottom Sniping" in algorithmic trading—finding rare, highly 
asymmetric market inflection points.

Key Concepts for ML Beginners:
1. **Genetic Algorithm (GA)**: Instead of training one massive model, we train a 
   "population" of 1,200 tiny models. The best models survive and combine their 
   "genes" (technical indicators) to create the next generation.
2. **Tri-Split Validation**: To prevent the model from memorizing the past 
   (overfitting), data is split chronologically into Train (learn weights), 
   Tune (learn thresholds), and Out-of-Sample (evaluate fitness).
3. **Regime Awareness**: Markets change (e.g., bull vs. bear, high vs. low 
   volatility). This engine evaluates how well a gene performs across 6 
   distinct market "regimes" to prevent feature dilution.
4. **GPU Vectorization**: To process 1,200 models simultaneously, all 
   evolutionary logic and neural network training is matrix-multiplied on 
   the GPU, bypassing slow Python loops.
"""

import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
import numpy as np
import threading
import queue
import os
import fnmatch

# Global queue to handle background file saving
log_queue = queue.Queue(maxsize=100)

def async_sink_worker():
    """Consumes data from the logging queue to decouple I/O from the GPU.
    
    ML Beginner Note:
        Saving files to a hard drive (Disk I/O) is extremely slow compared 
        to GPU calculations. This function runs on a separate CPU background thread.
        It waits for the GPU to send data (like model weights or log lines) to a 
        queue, and saves them to disk without pausing the main training loop.
    """
    os.makedirs('checkpoints', exist_ok=True)
    os.makedirs('logs', exist_ok=True)
    while True:
        item = log_queue.get()
        if item is None: break
        filename, data, is_model = item
        try:
            if is_model:
                # Direct overwrite to prevent disk bloat for the latest population state
                torch.save(data, f"checkpoints/{filename}")
            else:
                with open(f"logs/{filename}", "a") as f:
                    f.write(f"{data}\n")
        except Exception as e:
            print(f"❌ [Sink Error]: {e}")
        finally:
            log_queue.task_done()



class FocalLoss(nn.Module):
    """Custom loss function for highly imbalanced datasets.
    
    ML Beginner Note:
        Standard Binary Cross Entropy (BCE) struggles when the target event 
        (e.g., a market bottom) is very rare (e.g., 1% of the time). The model 
        will just learn to predict "No bottom" 100% of the time to get 99% accuracy.
        Focal loss solves this by mathematically down-weighting the easily 
        classified "normal" background noise, forcing the model to focus on the rare events.
    """
    
    def __init__(self, alpha=0.99, gamma=3.0):
        """Initializes the FocalLoss module.
        
        Args:
            alpha (float): Balances the importance of positive vs. negative classes.
                           0.99 heavily forces the network to care about the rare positive class.
            gamma (float): The focusing parameter. Higher values exponentially 
                           discount easy-to-classify examples.
        """
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma

    def forward(self, inputs, targets):
        """Calculates the focal loss between predictions and targets.

        Args:
            inputs (torch.Tensor): Raw logits (un-normalized predictions) from the neural network.
            targets (torch.Tensor): The ground truth binary labels (0 or 1).

        Returns:
            torch.Tensor: A scalar tensor representing the mean focal loss.
        """
        bce_loss = F.binary_cross_entropy_with_logits(inputs, targets, reduction='none')
        probs = torch.sigmoid(inputs)
        # pt is the probability of the true class. If target is 1, it's probs. If 0, it's 1 - probs.
        pt = torch.where(targets == 1.0, probs, 1.0 - probs)
        return (self.alpha * (1.0 - pt)**self.gamma * bce_loss).mean()

class PersistentReactor:
    """The core hybrid Machine Learning engine (Neural Nets + GA).
    
    This class manages a population of neural networks, feeds them time-series 
    data, evaluates their performance, and naturally selects the best combinations 
    of inputs (genes) over thousands of generations.
    """
    
    def __init__(self, feature_df, target_series, config, device):
        """Initializes the Reactor, loads data to GPU, and creates the first generation.

        Args:
            feature_df (pd.DataFrame): The raw historical technical indicators.
            target_series (pd.Series): The ground truth labels to predict.
            config (dict): Hyperparameters and configuration settings.
            device (torch.device): The hardware device (CPU or CUDA/GPU) to run calculations on.
        """
        self.config = config
        self.device = device
        
        expanded_df = feature_df
        self.unique_inds = expanded_df.columns.tolist()
        
        # Convert pandas dataframes to PyTorch tensors and send them directly to GPU VRAM
        vals = np.nan_to_num(expanded_df.values.astype(np.float32))
        self.lake = torch.tensor(vals, device=device)
        self.y_all = torch.tensor(target_series.values.astype(np.float32), device=device).view(1, -1, 1)

        self.num_indicators = len(self.unique_inds)
        self.hidden_dim = config.get("HIDDEN_DIM", 128)
        
        # O(1) GENE FAMILY PRECOMPUTATION
        # ML Beginner Note: Dictionaries provide instant O(1) lookups instead of slow list scanning.
        self.gene_family_map = {}
        for i, name in enumerate(self.unique_inds):
            self.gene_family_map[i] = self._determine_family(name)
            
        # RESOLVE FORCED GENES (Indicators that MUST be included in every model)
        raw_forced = self.config.get("FORCED_GENES", [])
        resolved_indices = []
        for pattern in raw_forced:
            for i, ind_name in enumerate(self.unique_inds):
                if fnmatch.fnmatch(ind_name.lower(), pattern.lower()):
                    resolved_indices.append(i)
        
        self.forced_indices = torch.tensor(list(set(resolved_indices)), device=device).long()
        self.num_forced = len(self.forced_indices)
        self.available_pool = [i for i in range(self.num_indicators) if i not in resolved_indices]

        p_size = config.get("POP_SIZE", 1200)
        g_count = config.get("GENE_COUNT", 24)
        
        # INITIAL POPULATION
        # Create 1,200 unique combinations of 24 indicators
        indices_list = []
        for _ in range(p_size):
            free_slots = g_count - self.num_forced
            rand_idx = np.random.choice(self.available_pool, free_slots, replace=False)
            genome = torch.cat([self.forced_indices, torch.tensor(rand_idx, device=device)])
            indices_list.append(genome)

        self.population = torch.stack(indices_list).to(device).long()
        self.thresholds = torch.full((p_size,), 0.7, device=device) 

        # NEURAL NETWORK WEIGHT INITIALIZATION
        # W1: Input to Hidden Layer | W2: Hidden Layer to Output (Prediction)
        self.pop_W1 = torch.randn(p_size, g_count, self.hidden_dim, device=device) * 0.15
        self.pop_B1 = torch.zeros(p_size, 1, self.hidden_dim, device=device)
        self.pop_W2 = torch.randn(p_size, self.hidden_dim, 1, device=device) * 0.15
        self.pop_B2 = torch.zeros(p_size, 1, 1, device=device)
        
        # REGIME CONDITIONING MATRIX [6 Regimes x N Genes]
        self.global_density = self.y_all.mean().item()
        self.global_vol = self.lake.std().item()
        self.num_regimes = 6
        self.gene_scores = torch.zeros(self.num_regimes, self.num_indicators, device=device)
        self.gene_usage = torch.zeros(self.num_regimes, self.num_indicators, device=device)
        self.decay_factor = self.config.get("VITALITY_DECAY", 0.95)

    def load_checkpoint(self, filepath):
        """Restores the full evolutionary state to resume training safely.
        
        Args:
            filepath (str): Path to the saved .pt file.
            
        Returns:
            tuple: (current_generation_integer, best_f1_score_float)
        """
        ckpt = torch.load(filepath, map_location=self.device)
        self.population.copy_(ckpt['population'].to(self.device))
        self.pop_W1.copy_(ckpt['W1'].to(self.device))
        self.pop_W2.copy_(ckpt['W2'].to(self.device))
        self.pop_B1.copy_(ckpt['B1'].to(self.device))
        self.pop_B2.copy_(ckpt['B2'].to(self.device))
        self.thresholds.copy_(ckpt['thresholds'].to(self.device))
        self.gene_scores.copy_(ckpt['gene_scores'].to(self.device))
        self.gene_usage.copy_(ckpt['gene_usage'].to(self.device))
        return ckpt['gen'], ckpt['best_ever']

    def _determine_family(self, name):
        """Maps an indicator string name to a broader category (family).

        Args:
            name (str): The name of the technical indicator.

        Returns:
            str: The category string (e.g., 'momentum', 'volatility').
        """
        name_lower = name.lower()
        for fam, patterns in self.config.get('GENE_FAMILIES', {}).items():
            if any(p in name_lower for p in patterns): return fam
        return 'unknown'

    def _forward(self, x, w1, b1, w2, b2):
        """Batched forward pass for the Neural Networks.
        
        ML Beginner Note:
            `torch.bmm` is Batch Matrix Multiplication. Instead of running a 
            for-loop over 1,000 different models, we multiply all of them against 
            the data at the exact same time using the massive parallel cores of the GPU.

        Args:
            x, w1, b1, w2, b2: Tensors for inputs, weights, and biases.

        Returns:
            torch.Tensor: The un-normalized predictions (logits).
        """
        h1 = F.leaky_relu(torch.bmm(x, w1) + b1, 0.1)
        return torch.bmm(h1, w2) + b2

    def _apply_clustering_penalty(self, signals, f1_scores):
        """Penalizes models that fire multiple 'buy' signals too close together.
        
        ML Beginner Note:
            A 1D Convolution acts like a sliding window. Here, a 5-bar window 
            slides across the predictions. If the model predicted more than 1 bottom 
            inside any 5-bar period, it is considered "clustering" (machine-gunning).
            We exponentially decay its score so it learns to wait for true bottoms.

        Args:
            signals (torch.Tensor): Binary predictions [0, 1] over time.
            f1_scores (torch.Tensor): The current fitness scores for the models.

        Returns:
            torch.Tensor: The adjusted (penalized) fitness scores.
        """
        if signals.sum() == 0: return f1_scores
        
        # Capture original shape to handle tuning vs evaluation modes
        # Tuning: [Batch, Time, 1] | Evaluation: [Batch, Time, 1]
        orig_shape = signals.shape 
        
        # Reshape to [Batch, 1, Time] for Conv1d
        sig_tensor = signals.view(orig_shape[0], 1, orig_shape[1])
        
        kernel = torch.ones(1, 1, 5, device=self.device)
        
        # Density tells us how many signals are in the 5-bar window
        density = F.conv1d(sig_tensor.float(), kernel, padding=2)
        
        # We only penalize when density > 1 (more than one signal in 5 bars)
        # We multiply by sig_tensor so we only penalize the actual signal bits
        cluster_violations = F.relu(density - 1.0) * sig_tensor
        
        # Sum violations across time (dimension 2)
        total_cluster_weight = cluster_violations.sum(dim=2).view(-1)
        
        penalty_factor = torch.exp(-total_cluster_weight * 0.15) 
        
        # Reshape penalty to match f1_scores (usually [Batch] or [Batch, 1])
        return f1_scores.view(-1) * penalty_factor

    def run_generation(self):
        """Executes one full cycle of training, tuning, and Out-Of-Sample validation.

        Returns:
            dict: Metrics dictionary containing F1, Precision, Recall, and total Signals.
        """
        pop_size = self.config.get("POP_SIZE", 1200)
        chunk_size = self.config.get("GPU_CHUNK", 1024)
        prec_exp = self.config.get('PRECISION_EXP', 6)  
        min_sigs = self.config.get('MIN_SIGNALS', 3)
        
        metrics = {"f1": [], "prec": [], "rec": [], "sigs": []}
        criterion = FocalLoss(
            alpha=self.config.get("FOCAL_ALPHA", 0.99), 
            gamma=self.config.get("FOCAL_GAMMA", 3.0)
        ).to(self.device)
        
        total_len = len(self.lake)
        master_oos_start = int(total_len * self.config.get("OOS_BOUNDARY", 0.75))

        self.gene_scores *= self.decay_factor
        self.gene_usage *= self.decay_factor

        for i in range(0, pop_size, chunk_size):
            end_i = min(i + chunk_size, pop_size)
            curr_chunk = end_i - i
            indices = self.population[i:end_i]

            # DYNAMIC TRI-SPLIT VALIDATION (Train / Tune / OOS)
            window_end = torch.randint(int(master_oos_start * 0.5), master_oos_start, (1,)).item()
            w_len = int(window_end * self.config.get("LOOKBACK_WINDOW", 0.35))
            window_start = max(0, window_end - w_len)
            
            train_split = window_start + int(w_len * 0.60)
            tune_split = window_start + int(w_len * 0.80)

            # DYNAMIC REGIME DETECTION (Categorizing market conditions)
            w_density = self.y_all[:, window_start:train_split, :].mean().item()
            den_id = 0 if w_density < self.global_density * 0.5 else 2 if w_density > self.global_density * 1.5 else 1
            w_vol = self.lake[window_start:train_split].std().item()
            vol_id = 0 if w_vol < self.global_vol else 1
            regime_id = (den_id * 2) + vol_id  

            # Slice the data via PyTorch advanced indexing
            x_train = self.lake[window_start:train_split, indices].permute(1, 0, 2)
            y_train = self.y_all[:, window_start:train_split, :].expand(curr_chunk, -1, -1)
            x_tune = self.lake[train_split:tune_split, indices].permute(1, 0, 2)
            y_tune = self.y_all[:, train_split:tune_split, :].expand(curr_chunk, -1, -1)

            # Enable gradient calculation for training
            w1 = self.pop_W1[i:end_i].detach().requires_grad_(True)
            b1 = self.pop_B1[i:end_i].detach().requires_grad_(True)
            w2 = self.pop_W2[i:end_i].detach().requires_grad_(True)
            b2 = self.pop_B2[i:end_i].detach().requires_grad_(True)
            optimizer = optim.Adam([w1, b1, w2, b2], lr=self.config.get("LEARNING_RATE", 0.001))
            
            # --- TRAINING LOOP ---
            for _ in range(self.config.get("EPOCHS", 10)):
                optimizer.zero_grad()
                logits = self._forward(x_train, w1, b1, w2, b2)
                # Loss includes a slight penalty for predicting 1 too often (sparsity penalty)
                loss = criterion(logits, y_train) + (torch.mean(torch.sigmoid(logits)) * 0.5)
                loss.backward()
                torch.nn.utils.clip_grad_norm_([w1, b1, w2, b2], 1.0)
                optimizer.step()

            # --- POST-TRAINING OPERATIONS ---
            with torch.no_grad():
                self.pop_W1[i:end_i].copy_(w1)
                self.pop_W2[i:end_i].copy_(w2)
                self.pop_B1[i:end_i].copy_(b1)
                self.pop_B2[i:end_i].copy_(b2)

                tune_probs = torch.sigmoid(self._forward(x_tune, w1, b1, w2, b2))
                bt = torch.full((curr_chunk,), 0.7, device=self.device)
                mf1 = torch.zeros(curr_chunk, device=self.device)
                
                # Resolving at 100 points for finer threshold tuning on Tune Block
                for t in np.linspace(0.65, 0.95, 100):
                    p = (tune_probs > t).float()
                    tp, fp, fn = (p * y_tune).sum(1), (p * (1 - y_tune)).sum(1), ((1 - p) * y_tune).sum(1)
                    
                    prec = tp / (tp + fp + 1e-8)
                    rec = tp / (tp + fn + 1e-8)

                    denom = prec + rec
                    
                    # Ensure f1_weighted is 1D [Batch]
                    f1_weighted = torch.where(denom > 0, (2 * (prec**prec_exp * rec)) / denom, torch.zeros_like(denom)).view(-1)
                    
                    # Apply penalty - now both are 1D vectors of size [Batch]
                    f1_weighted = self._apply_clustering_penalty(p, f1_weighted)
                    
                    mask = f1_weighted > mf1 # No .view(-1) needed here now
                    mf1[mask] = f1_weighted[mask]
                    bt[mask] = t
                
                self.thresholds[i:end_i].copy_(bt)

                # --- MASTER OOS AUDIT (The True Test) ---
                x_test = self.lake[master_oos_start:, indices].permute(1, 0, 2)
                y_test = self.y_all[:, master_oos_start:, :].expand(curr_chunk, -1, -1)
                test_p = (torch.sigmoid(self._forward(x_test, w1, b1, w2, b2)) > bt.view(-1, 1, 1)).float()

                sigs_s = test_p.sum(1).view(-1)
                tp_t = (test_p * y_test).sum(1).view(-1)
                fp_t = (test_p * (1 - y_test)).sum(1).view(-1)
                fn_t = ((1 - test_p) * y_test).sum(1).view(-1)
                
                prec_s = tp_t / (tp_t + fp_t + 1e-8)
                rec_s = tp_t / (tp_t + fn_t + 1e-8)
                denom_s = prec_s + rec_s
                
                f1_s = torch.where(denom_s > 0, (2 * (prec_s**prec_exp * rec_s)) / denom_s, torch.zeros_like(denom_s))
                
                # Apply Signal Floor: Zero-out score if it didn't fire at least MIN_SIGNALS
                f1_s *= (sigs_s >= min_sigs).float()
                f1_s = self._apply_clustering_penalty(test_p, f1_s)
                
                # VECTORIZED REGIME-SPECIFIC GENE SCORING
                # ML Beginner Note: scatter_add_ is an ultra-fast way to map the fitness scores 
                # of entire neural networks back to the specific genes (indicators) that built them.
                flat_indices = indices.view(-1)
                expanded_f1 = f1_s.view(-1, 1).expand(-1, indices.size(1)).reshape(-1)
                self.gene_scores[regime_id].scatter_add_(0, flat_indices, expanded_f1)
                self.gene_usage[regime_id].scatter_add_(0, flat_indices, torch.ones_like(expanded_f1))

                metrics["f1"].append(f1_s.cpu())
                metrics["prec"].append(prec_s.cpu())
                metrics["rec"].append(rec_s.cpu())
                metrics["sigs"].append(sigs_s.cpu())
                torch.cuda.empty_cache()

        return {k: torch.cat(v) for k, v in metrics.items()}

    

    def evolve(self, fitness_scores):
        """Applies Genetic Algorithm principles to create the next generation of models.
        
        This handles sorting by fitness, Elitism (keeping the best), Tournament Selection,
        Crossover (swapping genes), Diversity Enforcement, and Mutating neural network weights.

        Args:
            fitness_scores (torch.Tensor): 1D array of Out-Of-Sample F1 scores.
        """
        pop_size = self.config.get("POP_SIZE", 1200)
        idx = torch.argsort(fitness_scores, descending=True)
        
        # Sort population and weights by fitness (best first)
        self.population = self.population[idx]
        self.pop_W1, self.pop_W2 = self.pop_W1[idx], self.pop_W2[idx]
        self.pop_B1, self.pop_B2 = self.pop_B1[idx], self.pop_B2[idx]
        self.thresholds = self.thresholds[idx]

        fit_mean = torch.mean(fitness_scores)
        fit_std = torch.std(fitness_scores) + 1e-8
        is_stagnant = ((fitness_scores[0] - fit_mean) / fit_std) < 1.1
        
        keep = max(2, pop_size // 10)  # Elitism: protect the top 10%
        new_pop = self.population.clone()
        new_w1 = self.pop_W1.clone()
        new_w2 = self.pop_W2.clone()
        
        # Calculate vitality (how historically good a gene is) across all regimes, taking the max
        vitality = ((self.gene_scores + 0.1) / (self.gene_usage + 1.0)).max(dim=0).values
        
        # --- TOURNAMENT SELECTION & CROSSOVER ---
        for i in range(keep, pop_size):
            # Pick 4 random competitors, find the best among them (twice) for p1 and p2
            t1, t2 = torch.randint(0, pop_size, (4,)), torch.randint(0, pop_size, (4,))
            p1, p2 = t1[torch.argmax(fitness_scores[t1])], t2[torch.argmax(fitness_scores[t2])]
            
            new_pop[i] = self.population[p1].clone()
            new_w1[i], new_w2[i] = self.pop_W1[p1].clone(), self.pop_W2[p1].clone()
            
            if self.num_forced > 0:
                new_pop[i, :self.num_forced] = self.forced_indices

            # 70-85% chance to perform crossover (swap tail-end genes between parents)
            if torch.rand(1).item() < (0.85 if is_stagnant else 0.7):
                cut = torch.randint(self.num_forced, self.config.get("GENE_COUNT", 24), (1,)).item()
                head = new_pop[i, :cut]
                tail = self.population[p2, cut:].clone()
                
                v_probs = vitality.softmax(0)
                # Resolve duplicate genes in the newly combined genome
                for g in range(len(tail)):
                    if tail[g] in head:
                        candidates = torch.multinomial(v_probs, min(50, len(v_probs)), replacement=False)
                        for cand in candidates:
                            if cand not in head and cand not in tail:
                                tail[g] = cand; break
                
                new_pop[i, cut:] = tail
                new_w1[i, cut:] = self.pop_W1[p2, cut:]

            # --- DIVERSITY ENFORCEMENT ---
            # Ensure the model relies on a mix of different indicators (volume, trend, etc.)
            curr_fams = {self.gene_family_map[g.item()] for g in new_pop[i]}
            diversity_targets = self.config.get('DIVERSITY_TARGETS', [])
            min_req = min(self.config.get('MIN_REQUIRED_FAMILIES', 3), len(diversity_targets))
            
            if len(curr_fams) < min_req:
                missing = [f for f in diversity_targets if f not in curr_fams]
                if missing:
                    target = np.random.choice(missing)
                    fam_pool = [ix for ix, name in enumerate(self.unique_inds) if self.gene_family_map[ix] == target and ix not in new_pop[i]]
                    if fam_pool:
                        slot = torch.randint(self.num_forced, self.config.get("GENE_COUNT", 24), (1,)).item()
                        probs = torch.softmax(vitality[fam_pool] * self.config.get('VITALITY_SOFTMAX_TEMP', 10.0), dim=0)
                        new_pop[i, slot] = fam_pool[torch.multinomial(probs, 1).item()]

        # --- RANK-BASED MUTATION ---
        # Elites get micro-mutations. Bottom tier gets heavy structural mutations.
        ranks = torch.arange(pop_size - keep, device=self.device).float() / (pop_size - keep - 1 + 1e-8)
        rank_multiplier = torch.exp(ranks * 2.0).view(-1, 1, 1) 
        base_mut_rate = self.config.get("WEIGHT_MUTATION_RATE", 0.02) * (5.0 if is_stagnant else 1.0)
        dynamic_mut_matrix = base_mut_rate * rank_multiplier
        
        new_w1[keep:] += torch.randn_like(new_w1[keep:]) * dynamic_mut_matrix
        new_w2[keep:] += torch.randn_like(new_w2[keep:]) * dynamic_mut_matrix

        self.population.copy_(new_pop)
        self.pop_W1.copy_(new_w1)
        self.pop_W2.copy_(new_w2)

        # GENOME COLLAPSE AUTO-HEAL
        # If a bug causes a network to have duplicate genes, overwrite it with a fresh random one.
        gene_count = self.config.get("GENE_COUNT", 24)
        for g_idx in range(pop_size):
            if len(torch.unique(self.population[g_idx])) != gene_count:
                free_slots = gene_count - self.num_forced
                rand_idx = np.random.choice(self.available_pool, free_slots, replace=False)
                healed_genome = torch.cat([self.forced_indices, torch.tensor(rand_idx, device=self.device)])
                self.population[g_idx] = healed_genome

    def run_atomic_scan(self, top_n_vitality=40, scan_size=6):
        """100% Pure GPU Atomic Scan: Batched random sampling without replacement.
        
        ML Beginner Note:
            If the system gets "stuck" (local minima), we take the top 40 best historically
            performing genes and force random combinations of them into the bottom 20% 
            of the population. It injects strong new ideas into the gene pool.

        Args:
            top_n_vitality (int): How many of the historically best genes to sample from.
            scan_size (int): Number of genes to sample per new injection.
        """
        vitality = ((self.gene_scores + 0.1) / (self.gene_usage + 1.0)).max(dim=0).values
        top_genes = torch.argsort(vitality, descending=True)
        
        mask = ~torch.isin(top_genes, self.forced_indices)
        pool = top_genes[mask][:top_n_vitality]
        
        if len(pool) < scan_size: return

        pop_size = self.config.get("POP_SIZE", 1200)
        num_to_replace = pop_size // 5 
        start_idx = max(0, pop_size - num_to_replace)
        actual_replace = pop_size - start_idx
        
        free_slots = self.config.get("GENE_COUNT", 24) - self.num_forced
        
        # Pure GPU Vectorized Monte Carlo Sampling
        rand_weights = torch.rand(actual_replace, len(pool), device=self.device)
        sampled_pool_indices = torch.topk(rand_weights, free_slots, dim=1).indices
        sampled_genes = pool[sampled_pool_indices]
        
        expanded_forced = self.forced_indices.unsqueeze(0).expand(actual_replace, -1)
        new_genomes = torch.cat([expanded_forced, sampled_genes], dim=1)
        
        self.population[start_idx:] = new_genomes
        # Initialize fresh weights and wipe the ghost biases for the newly injected networks
        self.pop_W1[start_idx:] = torch.randn(actual_replace, self.config.get("GENE_COUNT", 24), self.hidden_dim, device=self.device) * 0.15
        self.pop_W2[start_idx:] = torch.randn(actual_replace, self.hidden_dim, 1, device=self.device) * 0.15
        self.pop_B1[start_idx:] = torch.zeros(actual_replace, 1, self.hidden_dim, device=self.device)
        self.pop_B2[start_idx:] = torch.zeros(actual_replace, 1, 1, device=self.device)