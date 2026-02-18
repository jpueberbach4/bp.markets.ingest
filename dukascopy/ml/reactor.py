import torch
import torch.nn.functional as F
import numpy as np
import time

class PersistentReactor:
    def __init__(self, feature_df, target_series, config, device):
        self.config = config  # store config
        self.device = device  # GPU or CPU
        self.dtype = torch.float32  # use float32 numbers
        self.stream = torch.cuda.Stream()  # create a CUDA stream for async ops
        
        vals = feature_df.values.astype(np.float32)  # convert pandas to numpy float32
        vals = np.nan_to_num(vals, nan=0.0, posinf=0.0, neginf=0.0)  # replace NaN/inf with 0
        
        self.split = int(len(vals) * 0.8)  # split 80% train / 20% test
        train_subset = vals[:self.split, :]  # take first 80% for training stats
        mu = np.mean(train_subset, axis=0)  # mean per column
        sigma = np.std(train_subset, axis=0)  # std per column
        vals = (vals - mu) / (sigma + 1e-6)  # normalize data
        vals = np.clip(vals, -5.0, 5.0)  # prevent crazy outliers
        vals = np.nan_to_num(vals, nan=0.0)  # just in case NaNs remain
        
        padding = np.zeros((vals.shape[0], 1), dtype=np.float32)  # extra column for padding
        self.lake = torch.tensor(np.hstack([vals, padding]), device=device, dtype=self.dtype)  # convert to torch
        self.pad_idx = self.lake.shape[1] - 1  # index of padding column
        
        self.col_names = list(feature_df.columns)  # store column names
        ind_map = {col.split('___')[0]: [] for col in self.col_names}  # map indicator name -> columns
        for i, col in enumerate(self.col_names):
            ind_map[col.split('___')[0]].append(i)  # append column index to indicator
        
        self.unique_inds = list(ind_map.keys())  # list of indicators
        self.num_indicators = len(self.unique_inds)  # number of unique indicators
        
        decoder_np = np.full((self.num_indicators, config['MAX_COLS_PER_IND']), self.pad_idx, dtype=np.int32)  # fill decoder with padding
        for i, ind in enumerate(self.unique_inds):
            c = ind_map[ind][:config['MAX_COLS_PER_IND']]  # take first few columns for indicator
            decoder_np[i, :len(c)] = c  # store them in decoder
        self.decoder = torch.tensor(decoder_np, device=device, dtype=torch.long)  # make decoder a torch tensor
        
        y_raw = torch.tensor(target_series.values, device=device).float().view(1, -1, 1)  # target values
        self.y_train = y_raw[:, :self.split, :]  # training target
        self.y_test = y_raw[:, self.split:, :]  # test target

        hidden = 128  # number of hidden neurons
        self.pop_W1 = (torch.randn(config['POP_SIZE'], config['TOTAL_INPUTS'], hidden, device=device) * 0.01)  # input->hidden weights
        self.pop_W2 = (torch.randn(config['POP_SIZE'], hidden, 1, device=device) * 0.01)  # hidden->output weights
        self.pop_B1 = torch.zeros(config['POP_SIZE'], 1, hidden, device=device)  # hidden biases
        self.pop_B2 = torch.full((config['POP_SIZE'], 1, 1), -0.5, device=device)  # output biases
        
        pop_indices = []
        for _ in range(config['POP_SIZE']):
            pop_indices.append(torch.randperm(self.num_indicators)[:config['GENE_COUNT']])  # random genes per individual
        self.population = torch.stack(pop_indices).to(device)  # make population tensor
        
        self.thresholds = torch.full((config['POP_SIZE'],), 0.1, device=device, dtype=self.dtype)  # activation thresholds

    def run_generation(self, do_profile=False):
        metrics = {'f1': [], 'prec': [], 'rec': [], 'sigs': []}  # store results
        lr = self.config['LEARNING_RATE']  # learning rate
        pos_weight = torch.tensor(200.0, device=self.device)  # weight for positive labels

        all_cols = self.decoder[self.population].view(self.config['POP_SIZE'], -1)  # get all columns per individual
        col_chunks = torch.split(all_cols, self.config['GPU_CHUNK'])  # split into GPU-friendly chunks
        n_chunks = len(col_chunks)
        
        for idx, chunk_cols in enumerate(col_chunks):
            vram = torch.cuda.memory_allocated(self.device) / 1024**3  # check VRAM usage
            print(f"  ⚡ [Chunk {idx+1:02d}/{n_chunks}] VRAM: {vram:.2f}GB | Throttled Math...", end="\r")
            
            start_i = idx * self.config['GPU_CHUNK']
            p_size = chunk_cols.size(0)
            
            W1 = self.pop_W1[start_i:start_i+p_size].detach().clone()  # copy weights for this chunk
            W2 = self.pop_W2[start_i:start_i+p_size].detach().clone()
            B1 = self.pop_B1[start_i:start_i+p_size].detach().clone()
            B2 = self.pop_B2[start_i:start_i+p_size].detach().clone()
            
            X_batch = self.lake[:self.split, chunk_cols].permute(1, 0, 2)  # get input data for this chunk
            Y_batch = self.y_train.expand(p_size, -1, -1)  # replicate targets for batch

            for epoch in range(self.config['EPOCHS']):  # training loop
                H1 = F.leaky_relu(torch.bmm(X_batch, W1) + B1, 0.1)  # hidden layer
                logits = torch.bmm(H1, W2) + B2  # output layer
                logits = torch.clamp(logits, -15.0, 15.0)  # prevent extreme numbers

                if torch.isnan(logits).any():  # check for NaNs
                    W1.fill_(0.0); W2.fill_(0.0)
                    break
            
                pred = torch.sigmoid(logits)  # convert to probabilities
                weight_mask = torch.where(Y_batch > 0.5, pos_weight, torch.tensor(1.0, device=self.device))  # weight positive labels more
                d_out = (pred - Y_batch) * weight_mask  # error signal
                
                gnorm = torch.norm(d_out)  # gradient norm
                if gnorm > 1.0:
                    d_out = d_out / (gnorm + 1e-6)  # normalize gradient if too big
                
                W2.sub_(torch.bmm(H1.transpose(1, 2), d_out) * lr)  # update hidden->output weights
                B2.sub_(d_out.sum(dim=1, keepdim=True) * lr)  # update output bias
                d_h1 = torch.bmm(d_out, W2.transpose(1, 2)) * (H1 > 0.1)  # hidden layer gradient
                W1.sub_(torch.bmm(X_batch.transpose(1, 2), d_h1) * lr)  # update input->hidden weights
                B1.sub_(d_h1.sum(dim=1, keepdim=True) * lr)  # update hidden bias

            self.pop_W1[start_i:start_i+p_size].copy_(W1)  # save updated weights
            self.pop_W2[start_i:start_i+p_size].copy_(W2)
            self.pop_B1[start_i:start_i+p_size].copy_(B1)
            self.pop_B2[start_i:start_i+p_size].copy_(B2)

            with torch.no_grad():
                X_test = self.lake[self.split:, chunk_cols].permute(1, 0, 2)  # test inputs
                logits_test = torch.bmm(F.leaky_relu(torch.bmm(X_test, W1) + B1, 0.1), W2) + B2
                preds = (torch.sigmoid(logits_test) > self.thresholds[start_i:start_i+p_size].view(-1,1,1)).float()  # thresholded outputs
                
                Y_test = self.y_test.expand(p_size, -1, -1)  # test targets
                tp = (preds * Y_test).sum(1)  # true positives
                fp = (preds * (1 - Y_test)).sum(1)  # false positives
                fn = ((1 - preds) * Y_test).sum(1)  # false negatives
                
                metrics['f1'].append((2 * tp) / (2 * tp + fp + fn + 1e-6))  # f1 score
                metrics['prec'].append(tp / (tp + fp + 1e-6))  # precision
                metrics['rec'].append(tp / (tp + fn + 1e-6))  # recall
                metrics['sigs'].append(preds.sum(1))  # number of active signals
            
            torch.cuda.empty_cache()  # free GPU memory

        return {k: torch.cat(v).view(-1) for k, v in metrics.items()}  # combine metrics

    def evolve(self, f1_scores):
        pop_size = self.config['POP_SIZE']
        idx = torch.argsort(f1_scores, descending=True)  # rank population by f1
        keep = pop_size // 10  # keep top 10%
        repeats = idx[:keep].repeat((pop_size // keep) + 1)[:pop_size]  # repeat elites
        
        self.population.copy_(self.population[repeats])  # copy elite genes
        self.thresholds.copy_(self.thresholds[repeats])  # copy elite thresholds
        
        rate = self.config['WEIGHT_MUTATION_RATE']
        for p in [self.pop_W1, self.pop_W2, self.pop_B1, self.pop_B2]:
            p.copy_(p[repeats] + torch.randn_like(p) * rate)  # mutate weights

        for i in range(keep, pop_size):  # mutate non-elite genes
            mut_mask = torch.rand(self.config['GENE_COUNT'], device=self.device) < 0.1  # random mutation mask
            if mut_mask.any():
                current_genes = self.population[i].tolist()
                available_pool = [g for g in range(self.num_indicators) if g not in current_genes]  # pick genes not already in chromosome
                
                if available_pool:
                    num_to_replace = mut_mask.sum().item()
                    new_picks = np.random.choice(available_pool, min(len(available_pool), int(num_to_replace)), replace=False)
                    mut_indices = torch.where(mut_mask)[0]
                    for m_idx, g_val in zip(mut_indices, new_picks):
                        self.population[i, m_idx] = int(g_val)  # apply mutation
