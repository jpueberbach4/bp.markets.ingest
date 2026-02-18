import torch
import numpy as np
import cProfile
import pstats
import io

class PersistentReactor:
    def __init__(self, feature_df, target_series, config, device):
        self.config = config
        self.device = device
        self.dtype = torch.float16 
        self.stream = torch.cuda.Stream()
        
        # Lake & Normalization
        vals = feature_df.values.astype(np.float32)
        vals = (vals - np.mean(vals, axis=0)) / (np.std(vals, axis=0) + 1e-6)
        padding = np.zeros((vals.shape[0], 1), dtype=np.float32)
        self.lake = torch.tensor(np.hstack([vals, padding]), device=device).to(self.dtype)
        self.pad_idx = self.lake.shape[1] - 1
        
        # Decoder
        self.col_names = list(feature_df.columns)
        ind_map = {col.split('___')[0]: [] for col in self.col_names}
        for i, col in enumerate(self.col_names):
            ind_map[col.split('___')[0]].append(i)
        
        self.unique_inds = list(ind_map.keys())
        self.num_indicators = len(self.unique_inds)
        
        decoder_np = np.full((self.num_indicators, config['MAX_COLS_PER_IND']), self.pad_idx, dtype=np.int32)
        for i, ind in enumerate(self.unique_inds):
            c = ind_map[ind][:config['MAX_COLS_PER_IND']]
            decoder_np[i, :len(c)] = c
        self.decoder = torch.tensor(decoder_np, device=device, dtype=torch.long)
        
        # Targets (FP32 for BCE Stability)
        y_raw = torch.tensor(target_series.values, device=device).abs().gt(0.5).float()
        self.split = int(len(vals) * 0.8)
        self.y_train_base = y_raw[:self.split].view(1, -1, 1)
        self.y_test_base = y_raw[self.split:].view(1, -1, 1)
        
        self.Y_train_exp = self.y_train_base.expand(config['GPU_CHUNK'], -1, -1)
        self.Y_test_exp = self.y_test_base.expand(config['GPU_CHUNK'], -1, -1)

        # Neural Populations (He Initialization)
        hidden = 128 
        self.pop_W1 = (torch.randn(config['POP_SIZE'], config['TOTAL_INPUTS'], hidden, device=device) * np.sqrt(2/config['TOTAL_INPUTS'])).to(self.dtype)
        self.pop_B1 = torch.zeros(config['POP_SIZE'], 1, hidden, device=device).to(self.dtype)
        self.pop_W2 = (torch.randn(config['POP_SIZE'], hidden, 1, device=device) * np.sqrt(2/hidden)).to(self.dtype)
        self.pop_B2 = torch.zeros(config['POP_SIZE'], 1, 1, device=device).to(self.dtype)
        
        # Genes & Thresholds
        self.population = torch.randint(0, self.num_indicators, (config['POP_SIZE'], config['GENE_COUNT']), device=device, dtype=torch.long)
        self.thresholds = torch.full((config['POP_SIZE'],), 0.5, device=device, dtype=self.dtype)

    def run_generation(self, do_profile=False):
        metrics = {'f1': [], 'prec': [], 'rec': [], 'sigs': []}
        lr = torch.tensor(self.config['LEARNING_RATE'], device=self.device, dtype=self.dtype)
        
        # FP32 Loss Constants
        pos_weight = torch.tensor(10.0, device=self.device, dtype=torch.float32)
        neg_weight = torch.tensor(1.0, device=self.device, dtype=torch.float32)

        if do_profile:
            pr = cProfile.Profile(); pr.enable()

        all_cols = self.decoder[self.population].view(self.config['POP_SIZE'], -1)
        col_chunks = torch.split(all_cols, self.config['GPU_CHUNK'])
        thresh_chunks = torch.split(self.thresholds, self.config['GPU_CHUNK'])

        with torch.cuda.stream(self.stream):
            for idx, chunk_cols in enumerate(col_chunks):
                start_i = idx * self.config['GPU_CHUNK']
                p_size = chunk_cols.size(0)
                
                W1, B1 = self.pop_W1[start_i:start_i+p_size], self.pop_B1[start_i:start_i+p_size]
                W2, B2 = self.pop_W2[start_i:start_i+p_size], self.pop_B2[start_i:start_i+p_size]
                chunk_thresh = thresh_chunks[idx].view(-1, 1, 1)
                
                X_train = self.lake[:self.split, chunk_cols].permute(1, 0, 2)
                Y_tgt = self.Y_train_exp[:p_size] if p_size < self.config['GPU_CHUNK'] else self.Y_train_exp
                
                for _ in range(self.config['EPOCHS']):
                    # Forward
                    H1 = torch.relu(torch.bmm(X_train, W1) + B1)
                    logits = torch.bmm(H1, W2) + B2
                    
                    # Numeric Stability Promotion
                    pred_f32 = torch.sigmoid(logits.float())
                    weight_mask = torch.where(Y_tgt > 0.5, pos_weight, neg_weight)
                    d_out_f32 = (pred_f32 - Y_tgt) * weight_mask
                    d_out = d_out_f32.to(self.dtype)
                    
                    # Backward
                    W2.sub_(torch.bmm(H1.transpose(1, 2), d_out) * lr)
                    B2.sub_(d_out.sum(dim=1, keepdim=True) * lr)
                    d_h1 = torch.bmm(d_out, W2.transpose(1, 2)) * (H1 > 0)
                    W1.sub_(torch.bmm(X_train.transpose(1, 2), d_h1) * lr)
                    B1.sub_(d_h1.sum(dim=1, keepdim=True) * lr)

                with torch.no_grad():
                    X_test = self.lake[self.split:, chunk_cols].permute(1, 0, 2)
                    Fin = torch.sigmoid(torch.bmm(torch.relu(torch.bmm(X_test, W1) + B1), W2) + B2)
                    Bin = (Fin > chunk_thresh).to(self.dtype)
                    Y_exp = self.Y_test_exp[:p_size] if p_size < self.config['GPU_CHUNK'] else self.Y_test_exp
                    
                    TP = (Bin * Y_exp).sum(1)
                    FP = (Bin * (1-Y_exp)).sum(1)
                    FN = ((1-Bin)*Y_exp).sum(1)
                    
                    metrics['f1'].append((2*TP)/(2*TP + FP + FN + 1e-6))
                    metrics['prec'].append(TP / (TP + FP + 1e-6))
                    metrics['rec'].append(TP / (TP + FN + 1e-6))
                    metrics['sigs'].append(Bin.sum(1))
            
            self.stream.synchronize()

        if do_profile:
            pr.disable()
            s = io.StringIO()
            pstats.Stats(pr, stream=s).sort_stats('cumulative').print_stats(10)
            print(s.getvalue())

        return {k: torch.cat(v).view(-1) for k, v in metrics.items()}

    def evolve(self, f1_scores):
        pop_size = self.config['POP_SIZE']
        idx = torch.argsort(f1_scores, descending=True)
        keep_count = pop_size // 10
        elites = idx[:keep_count]
        
        # This index map dictates which parents the next generation is born from
        repeats = elites.repeat((pop_size // keep_count) + 1)[:pop_size]
        
        # We MUST move the weights, genes, and thresholds together
        self.population.copy_(self.population[repeats])
        self.thresholds.copy_(self.thresholds[repeats])

        rate = self.config['WEIGHT_MUTATION_RATE']
        reset_threshold = pop_size // 2 

        # Proper Weight Inheritance & Rank-Aware Reset
        for param in [self.pop_W1, self.pop_W2, self.pop_B1, self.pop_B2]:
            # Inherit parent weights AND apply mutation
            # This restores the Lamarckian link between genes and trained weights
            parent_weights = param[repeats]
            noise = (torch.randn_like(parent_weights) * rate).to(self.dtype)
            param.copy_(parent_weights + noise)
            
            # Darwinian Reset (Now correctly applied to the bottom 50% of offspring)
            # The top 50% are clones/mutations of elites; the bottom are fresh starts
            if param.dim() == 3: # Weights
                # Re-initialize using He initialization logic for the reset portion
                fan_in = param.shape[1]
                std = np.sqrt(2 / fan_in)
                param[reset_threshold:].copy_((torch.randn_like(param[reset_threshold:]) * std).to(self.dtype))
            else: # Biases
                param[reset_threshold:].zero_()

        # Threshold Evolution (Elite Protected)
        # top keep_count are protected from drift
        thresh_noise = (torch.randn_like(self.thresholds) * 0.05)
        thresh_noise[:keep_count] = 0 
        self.thresholds.add_(thresh_noise).clamp_(0.01, 0.99)

        # Gene Mutation (Indicator Swap)
        # Protect elites from losing their indicator combinations
        mut_mask = torch.rand(self.population.shape, device=self.device) < 0.1
        mut_mask[:keep_count] = False 
        self.population[mut_mask] = torch.randint(0, self.num_indicators, (mut_mask.sum(),), device=self.device)