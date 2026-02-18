import torch
import torch.nn.functional as F
import pandas as pd
import numpy as np
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ingest import IndicatorIngestor

CONFIG = {
    'BASE_URL': "http://localhost:8000/ohlcv/1.1",
    'SYMBOL': "EUR-USD",
    'TIMEFRAME': "4h",
    'TARGET_INDICATOR': "example-pivot-finder",
    'START_DATE': "2018-01-01",
    'END_DATE': "2026-01-01",
    'MAX_COLS_PER_IND': 1,
    'FORCED_INDICATORS': [],           
    'BLACKLISTED_INDICATORS': []       
}

DEVICE = torch.device("cpu")

def validate(checkpoint_path):
    if not os.path.exists(checkpoint_path):
        print(f"❌ File {checkpoint_path} not found.")
        return

    print(f"📂 Loading Checkpoint: {checkpoint_path}")
    cp = torch.load(checkpoint_path, map_location=DEVICE)
    
    genes = cp['genes']
    weights = cp['state_dict']
    
    print(f"🧬 Model Genes: {genes}")

    # Fetch Universe
    ingestor = IndicatorIngestor(CONFIG)
    feature_df, target_series = ingestor.get_data()
    
    # Reactor Preprocessing (Bit-Perfect Mirror)
    vals = feature_df.values.astype(np.float32)
    vals = np.nan_to_num(vals, nan=0.0, posinf=0.0, neginf=0.0)
    
    # Calculate stats on 80% split
    split_idx = int(len(vals) * 0.8)
    train_subset = vals[:split_idx, :]
    mu = np.mean(train_subset, axis=0)
    sigma = np.std(train_subset, axis=0)
    
    vals = (vals - mu) / (sigma + 1e-6)
    vals = np.clip(vals, -5.0, 5.0)
    vals = np.nan_to_num(vals, nan=0.0)
    
    padding_col = np.zeros((vals.shape[0], 1), dtype=np.float32)
    lake_np = np.hstack([vals, padding_col])
    pad_idx = lake_np.shape[1] - 1
    
    # Mapping
    col_names = list(feature_df.columns)
    ind_map = {col.split('___')[0]: [] for col in col_names}
    for i, col in enumerate(col_names):
        ind_map[col.split('___')[0]].append(i)
        
    # Extract Columns for Genes
    selected_indices = []
    for gene in genes:
        if gene in ind_map:
            indices = ind_map[gene][:CONFIG['MAX_COLS_PER_IND']]
            while len(indices) < CONFIG['MAX_COLS_PER_IND']:
                indices.append(pad_idx)
            selected_indices.extend(indices)
        else:
            selected_indices.extend([pad_idx] * CONFIG['MAX_COLS_PER_IND'])
            
    # X_test extraction (matching Reactor.y_test logic)
    X_test_raw = lake_np[split_idx:, selected_indices]
    X_tensor = torch.tensor(X_test_raw, device=DEVICE).float().unsqueeze(0)
    Y_test_raw = target_series.values[split_idx:]

    # Forward Pass
    with torch.no_grad():
        W1, B1 = weights['W1'].to(DEVICE), weights['B1'].to(DEVICE)
        W2, B2 = weights['W2'].to(DEVICE), weights['B2'].to(DEVICE)
        threshold = weights.get('threshold', torch.tensor(0.1)).item()
        
        print(f"🧠 Brain Input: {W1.shape[0]} | Test Samples: {X_test_raw.shape[0]} | Threshold: {threshold:.4f}")

        H1 = F.leaky_relu(torch.bmm(X_tensor, W1.unsqueeze(0)) + B1, 0.1)
        logits = torch.bmm(H1, W2.unsqueeze(0)) + B2
        preds = (torch.sigmoid(logits) > threshold).float()

    # Report Generation (TEST SET ONLY)
    if isinstance(target_series.index[0], (int, np.integer)):
        full_times = pd.date_range(start=CONFIG['START_DATE'], periods=len(target_series), freq='4H')
    else:
        full_times = pd.to_datetime(target_series.index)
        
    test_times = full_times[split_idx:]

    results_df = pd.DataFrame({
        'time': test_times,
        'target': Y_test_raw,
        'pred': preds.view(-1).numpy()
    })
    
    results_df['month'] = results_df['time'].dt.to_period('M')
    
    print("\n" + "🚀 TEST SET VALIDATION (OUT-OF-SAMPLE)" + "\n" + "="*80)
    print(f"{'MONTH':<10} | {'SIGS':<5} | {'TP':<4} | {'FP':<4} | {'PREC':<8} | {'RECALL':<8}")
    print("-" * 80)
    
    for month, group in results_df.groupby('month'):
        sigs = int(group['pred'].sum())
        if sigs == 0: continue
        
        tp = ((group['pred'] == 1) & (group['target'] == 1)).sum()
        fp = ((group['pred'] == 1) & (group['target'] == 0)).sum()
        fn = ((group['pred'] == 0) & (group['target'] == 1)).sum()
        
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        
        print(f"{str(month):<10} | {sigs:<5} | {tp:<4} | {fp:<4} | {prec:7.2%} | {rec:7.2%}")

    total_sigs = int(results_df['pred'].sum())
    total_tp = ((results_df['pred'] == 1) & (results_df['target'] == 1)).sum()
    total_fp = ((results_df['pred'] == 1) & (results_df['target'] == 0)).sum()
    final_prec = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    
    print("-" * 80)
    print(f"TOTALS     | {total_sigs:<5} | {total_tp:<4} | {total_fp:<4} | {final_prec:7.2%}")
    print("="*80)

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "best_model_gen_8.pt"
    validate(target)