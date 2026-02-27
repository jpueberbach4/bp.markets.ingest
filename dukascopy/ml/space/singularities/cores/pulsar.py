
import torch
import torch.nn.functional as F
import numpy as np
import pandas as pd

from ml.space.base import Fabric

class PulsarCore(Fabric):
    """Encapsulates the heavy tensor mathematics and evolutionary logic."""

    def __init__(self, config, device, seed=42):
        self.config = config
        self.device = device
        self.seed = seed

        # Core hyperparameters
        self.pop_size = int(self.config.get('population_size', 1200))
        self.gene_count = int(self.config.get('gene_count', 16))
        self.hidden_dim = int(self.config.get('hidden_dim', 128))
        self.weight_mutation_rate = float(self.config.get("weight_mutation_rate", 0.005))
        self.verbose = bool(self.config.get("verbose", True))

        # Generators for reproducibility
        self.torch_generator = torch.Generator(device='cpu').manual_seed(self.seed)
        if self.device.type == 'cuda':
            self.cuda_generator = torch.Generator(device=self.device).manual_seed(self.seed)
        else:
            self.cuda_generator = self.torch_generator

        # Tensor State
        self.population = None  
        self.thresholds = None
        self.pop_W1 = None
        self.pop_B1 = None
        self.pop_W2 = None
        self.pop_B2 = None
        self.gene_scores = None
        self.gene_usage = None
        self.feature_names = None

    def init_population(self, num_indicators: int, feature_names: list):
        """Initializes the population genomes and neural weights."""
        self.feature_names = feature_names

        self.population = torch.stack([
            torch.tensor(
                np.random.choice(num_indicators, self.gene_count, replace=False),
                device=self.device
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
        self.thresholds = torch.full((self.pop_size,), 0.40, device=self.device)
        self.gene_scores = torch.zeros(num_indicators, device=self.device)
        self.gene_usage = torch.zeros(num_indicators, device=self.device)

    def forward(self, x, w1, b1, w2, b2):
        """Performs the Neural Network Forward Pass."""
        h1 = torch.bmm(x, w1)
        h1 = F.gelu(h1 + b1)
        return torch.bmm(h1, w2) + b2

    def evolve(self, latest_f1, latest_score):
        """Applies Elitism, Crossover, and Mutation to the population."""
        f1_scores = latest_f1.to(self.device).flatten()
        primary_scores = latest_score.to(self.device).flatten()
        
        gen_best_f1_val, gen_best_f1_idx = torch.max(f1_scores, dim=0)
        
        champ_pop = self.population[gen_best_f1_idx].clone()
        champ_w1 = self.pop_W1[gen_best_f1_idx].clone()
        champ_b1 = self.pop_B1[gen_best_f1_idx].clone()
        champ_w2 = self.pop_W2[gen_best_f1_idx].clone()
        champ_b2 = self.pop_B2[gen_best_f1_idx].clone()
        champ_thresh = self.thresholds[gen_best_f1_idx].clone()
        champ_f1 = gen_best_f1_val.clone()
        
        idx = torch.argsort(primary_scores, descending=True)
        
        self.population = self.population[idx]
        self.thresholds = self.thresholds[idx]
        self.pop_W1, self.pop_B1 = self.pop_W1[idx], self.pop_B1[idx]
        self.pop_W2, self.pop_B2 = self.pop_W2[idx], self.pop_B2[idx]
        f1_scores = f1_scores[idx] 
        
        keep = max(2, self.pop_size // 10)
        
        new_pop = self.population.clone()
        new_w1, new_b1 = self.pop_W1.clone(), self.pop_B1.clone()
        new_w2, new_b2 = self.pop_W2.clone(), self.pop_B2.clone()
        new_thresh = self.thresholds.clone()
        
        new_pop[1] = champ_pop
        new_w1[1], new_b1[1] = champ_w1, champ_b1
        new_w2[1], new_b2[1] = champ_w2, champ_b2
        new_thresh[1] = champ_thresh
        
        if self.verbose:
            self.print("CORE_QUANTUM_LOCK", f1=champ_f1.item())
            
        mutation_std = self.weight_mutation_rate
        
        for i in range(keep, self.pop_size):
            p1, p2 = torch.randint(0, keep, (2,), generator=self.torch_generator)
            
            if torch.rand(1, generator=self.torch_generator).item() < 0.7:
                cut = torch.randint(0, self.gene_count, (1,), generator=self.torch_generator).item()
                
                child_genes = torch.cat([
                    self.population[p1, :cut],
                    self.population[p2, cut:]
                ])
                
                unique_mask = torch.zeros(len(self.feature_names), dtype=torch.bool, device=self.device)
                unique_mask[child_genes] = True
                unique_count = unique_mask.sum().item()
                
                if unique_count < self.gene_count:
                    available_mask = ~unique_mask
                    available = torch.where(available_mask)[0].cpu().numpy()
                    fixed_genes = child_genes.unique().tolist()
                    needed = self.gene_count - len(fixed_genes)
                    if needed > 0 and len(available) >= needed:
                        new_genes = np.random.choice(available, needed, replace=False)
                        fixed_genes.extend(new_genes.tolist())
                        new_pop[i] = torch.tensor(fixed_genes, device=self.device)
                    else:
                        new_pop[i] = child_genes 
                else:
                    new_pop[i] = child_genes
                
                alpha = torch.rand(1, device=self.device, generator=self.cuda_generator) * 0.2 + 0.4
                new_w1[i] = alpha * self.pop_W1[p1] + (1 - alpha) * self.pop_W1[p2]
                new_w2[i] = alpha * self.pop_W2[p1] + (1 - alpha) * self.pop_W2[p2]
                new_thresh[i] = (
                    alpha * self.thresholds[p1]
                    + (1 - alpha) * self.thresholds[p2]
                )
            else:
                child_genes = self.population[p1].clone()
                if torch.rand(1, generator=self.torch_generator).item() < 0.3:
                    n_mutations = torch.randint(1, min(4, self.gene_count), (1,), generator=self.torch_generator).item()
                    current_unique_mask = torch.zeros(len(self.feature_names), dtype=torch.bool, device=self.device)
                    current_unique_mask[child_genes] = True
                    available_mask = ~current_unique_mask
                    available = torch.where(available_mask)[0].cpu().numpy()
                    
                    if len(available) >= n_mutations:
                        mutate_positions = torch.randperm(self.gene_count, generator=self.torch_generator)[:n_mutations]
                        new_genes = np.random.choice(available, n_mutations, replace=False)
                        for pos, new_gene in zip(mutate_positions, new_genes):
                            child_genes[pos] = new_gene
                
                new_pop[i] = child_genes
                
                new_w1[i] = self.pop_W1[p1] + torch.randn_like(self.pop_W1[p1]) * mutation_std
                new_w2[i] = self.pop_W2[p1] + torch.randn_like(self.pop_W2[p1]) * mutation_std
                new_thresh[i] = self.thresholds[p1] + torch.randn(1, device=self.device, generator=self.cuda_generator).squeeze() * 0.01
        
        all_genes = new_pop
        sorted_genes, _ = torch.sort(all_genes, dim=1)
        dup_mask = (sorted_genes[:, 1:] == sorted_genes[:, :-1]).any(dim=1)
        dup_indices = torch.where(dup_mask)[0].cpu().numpy()
        
        for i in dup_indices:
            genes = new_pop[i]
            unique_genes = genes.unique()
            fixed_genes = unique_genes.tolist()
            used_mask = torch.zeros(len(self.feature_names), dtype=torch.bool, device=self.device)
            used_mask[fixed_genes] = True
            available = torch.where(~used_mask)[0].cpu().numpy()
            needed = self.gene_count - len(fixed_genes)
            if needed > 0 and len(available) >= needed:
                new_genes = np.random.choice(available, needed, replace=False)
                fixed_genes.extend(new_genes.tolist())
                new_pop[i] = torch.tensor(fixed_genes, device=self.device)
                if self.verbose:
                    self.print("CORE_FIX_INDIVIDUAL", i=i)
        
        champ_exists = (new_pop == champ_pop.unsqueeze(0)).all(dim=1).any()
        if not champ_exists:
            if self.verbose:
                self.print("CORE_CHAMP_LOST")
            new_pop[1] = champ_pop
            new_w1[1], new_b1[1] = champ_w1, champ_b1
            new_w2[1], new_b2[1] = champ_w2, champ_b2
            new_thresh[1] = champ_thresh
        
        self.population = new_pop
        self.pop_W1, self.pop_B1 = new_w1, new_b1
        self.pop_W2, self.pop_B2 = new_w2, new_b2
        self.thresholds = torch.clamp(new_thresh, 0.10, 0.85)

    def run_atomic_scan(self):
        """Repopulates the weakest population members using high-vitality genes."""
        vitality = (self.gene_scores + 0.1) / (self.gene_usage + 1.0)
        pool_size = max(int(self.gene_count * 1.5), 40)
        pool_size = min(pool_size, len(self.feature_names))
        
        pool = torch.argsort(vitality, descending=True)[:pool_size]
        assert len(pool) == len(torch.unique(pool)), "Vitality pool contains duplicates!"
        
        start_idx = int(self.pop_size * 0.8)
        
        for i in range(start_idx, self.pop_size):
            self.population[i] = pool[
                torch.randperm(len(pool), generator=self.torch_generator)[:self.gene_count]
            ].to(self.device)
            
            self.pop_W1[i] = (
                torch.randn(self.gene_count, self.hidden_dim, device=self.device, generator=self.cuda_generator)
                * np.sqrt(2.0 / self.gene_count)
            )
            self.pop_W2[i] = (
                torch.randn(self.hidden_dim, 1, device=self.device, generator=self.cuda_generator)
                * np.sqrt(2.0 / self.hidden_dim)
            )
            self.pop_B2[i] = -2.0

    def emit(self, features: pd.DataFrame) -> np.ndarray:
        """Inference wrapper for the best individual."""
        if len(features) == 0:
            return np.array([])
        with torch.no_grad():
            x = torch.tensor(features.values.astype(np.float32), device=self.device)
            x_sel = x[:, self.population[0]].unsqueeze(0)
            logits = self.forward(
                x_sel,
                self.pop_W1[0:1],
                self.pop_B1[0:1],
                self.pop_W2[0:1],
                self.pop_B2[0:1],
            )
            return (torch.sigmoid(logits) > self.thresholds[0]).cpu().numpy().flatten()