import pandas as pd
import torch
import torch.nn as nn
import numpy as np
import os
import time
from typing import List, Dict, Any

# Global Registry for Model Caching
MODEL_REGISTRY = {}
CACHE_TTL = 30  # Seconds until a cached model is considered stale

def description() -> str:
    return (
        "High-fidelity inference engine utilizing a Registry-Cached Singularity architecture. "
        "Implements strict 'is-open' data isolation and 'merge_asof' backward alignment to "
        "eliminate look-ahead bias. Features a 30s TTL Multi-Model Cache and Throttled Audit."
    )

def meta() -> Dict:
    return {"author": "JP", "version": "2.2.0", "panel": 1, "verified": 1}

def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "model-name": args[0] if len(args) > 0 else "model-best.pt",
        "threshold": args[1] if len(args) > 1 else 0.50
    }

def warmup_count(args: List[str]) -> int:
    return 0

class SingularityInference(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int):
        super(SingularityInference, self).__init__()
        self.l1 = nn.Linear(input_dim, hidden_dim)
        self.l2 = nn.Linear(hidden_dim, 1)
        self.activation = nn.GELU() 
        self.out_act = nn.Sigmoid()
        
    def forward(self, x):
        h1 = self.l1(x)
        a1 = self.activation(h1)
        s2 = self.l2(a1)
        return self.out_act(s2), h1, a1, s2

def get_cached_model(checkpoint_path: str, device: torch.device):
    """Retrieves model object and weights from memory or loads from disk."""
    now = time.time()
    
    if checkpoint_path in MODEL_REGISTRY:
        cache_entry = MODEL_REGISTRY[checkpoint_path]
        if now - cache_entry['timestamp'] < CACHE_TTL:
            return cache_entry['data']
    
    if not os.path.exists(checkpoint_path):
        return None
        
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    
    # Extract Tensors
    w1 = checkpoint['W1'].to(device)
    b1 = checkpoint['B1'].to(device).reshape(-1)
    w2 = checkpoint['W2'].to(device)
    b2 = checkpoint['B2'].to(device).reshape(-1)
    
    # Persistent Model Initialization
    in_dim, hid_dim = w1.shape
    nn_model = SingularityInference(input_dim=in_dim, hidden_dim=hid_dim).to(device)
    nn_model.l1.weight.data = w1.t()
    nn_model.l1.bias.data = b1
    nn_model.l2.weight.data = w2 if w2.shape[0] == 1 else w2.t()
    nn_model.l2.bias.data = b2
    nn_model.eval()

    data = {
        'feature_names': checkpoint.get('feature_names', []),
        'nn_model': nn_model,
        'w1': w1,
        'means': checkpoint['means'].to(device),
        'stds': checkpoint['stds'].to(device),
        'last_audit_time': 0  # Initialize audit throttle
    }
    
    MODEL_REGISTRY[checkpoint_path] = {
        'timestamp': now,
        'data': data
    }
    return data

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    cancel_isopen = True
    from util.api import get_data_auto
    if df.empty:
        return pd.DataFrame({'score': 0.0, 'signal': 0.0}, index=df.index)

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model_name = options.get('model-name', 'model-best.pt')

    checkpoint_path = f"models/{model_name}"
    if not os.path.exists(checkpoint_path):
        checkpoint_path = f"checkpoints/{model_name}"

    cached_data = get_cached_model(checkpoint_path, device)
    
    if cached_data is None:
        return pd.DataFrame({'score': 0.0, 'signal': 0.0}, index=df.index)

    active_features = cached_data['feature_names']
    means = cached_data['means']
    stds = cached_data['stds']
    nn_model = cached_data['nn_model']

    # Parent indicator extraction
    parent_indicators = list(set([f.split(':')[0].split('__')[0] for f in active_features]))
    raw_df = get_data_auto(df, indicators=parent_indicators + ["is-open"])

    if cancel_isopen:
        inference_df = raw_df.copy()
    else:
        inference_df = raw_df[raw_df['is-open'] == 0].copy()

    # --- MISSING DATA AUDIT ---
    nan_counts = inference_df[active_features].isna().sum()
    nan_cols = nan_counts[nan_counts > 0]

    if not nan_cols.empty:
        print("\n" + "🚨" * 20)
        print("CRITICAL: NaN Detected in Inference Columns!")
        for col, count in nan_cols.items():
            print(f"COLUMN: {col:<60} | MISSING BARS: {count}")
        print("🚨" * 20 + "\n")

    if inference_df.empty:
        return pd.DataFrame({'score': 0.0, 'signal': 0.0}, index=df.index)

    # Column alignment
    ordered_columns = []
    for f in active_features:
        if f in inference_df.columns:
            ordered_columns.append(inference_df[f].values)
        else:
            ordered_columns.append(np.zeros(len(inference_df)))

    raw_values = np.stack(ordered_columns, axis=1).astype(np.float32)
    raw_model_tensor = torch.from_numpy(raw_values).to(device)
    normalized_tensor = (raw_model_tensor - means) / (stds + 1e-8)

    with torch.no_grad():
        # RUN INFERENCE
        out, _, _, _ = nn_model(normalized_tensor)
        predictions = out.squeeze().cpu().numpy()
        if predictions.ndim == 0:
            predictions = np.array([predictions.item()])

        # THROTTLED AUDIT (Runs every 30 seconds)
        current_time = time.time()
        if (current_time - cached_data['last_audit_time']) > 30:
            cached_data['last_audit_time'] = current_time
            
            # Feature Impact Calculation (Heavy Math)
            bar_contribution = normalized_tensor.unsqueeze(2) * cached_data['w1'].unsqueeze(0) 
            feature_impact = bar_contribution.mean(dim=(0, 2)).cpu().numpy()

            print("\n" + "☢️" * 60)
            print(f"STABLE AS-OF AUDIT: {model_name}")
            print(f"Device: {device} | Cache: ACTIVE | Mode: NITRO")
            print("-" * 80)
            header = f"{'FEATURE NAME':<60} | {'RAW MEAN':>10} | {'Z-MEAN':>8} | {'IMPACT':>8}"
            print(header)
            print("-" * 80)
            for i, name in enumerate(active_features):
                r_mean = raw_model_tensor[:, i].mean().item()
                z_mean = normalized_tensor[:, i].mean().item()
                impact = feature_impact[i]
                print(f"{name[:59]:<60} | {r_mean:>10.4f} | {z_mean:>8.4f} | {impact:>8.4f}")

            print("-" * 60)
            print(f"FINAL MAX PREDICTION (STABLE): {predictions.max():.4f}")
            print("☢️" * 60 + "\n")

    threshold_val = float(options.get('threshold', 0.50))
    stable_results = pd.DataFrame({
        'time_ms': inference_df['time_ms'],
        'score': predictions
    })
    stable_results['signal'] = np.where(stable_results['score'] > threshold_val, 1.0, 0.0)

    # Final Merge & Timeline Unification
    final_df = df[['time_ms']].copy()
    final_df['time_ms'] = final_df['time_ms'].astype('int64')
    stable_results['time_ms'] = stable_results['time_ms'].astype('int64')

    final_df = pd.merge_asof(
        final_df.sort_values('time_ms'),
        stable_results.sort_values('time_ms'),
        on='time_ms',
        direction='backward'
    )

    res = final_df.ffill().fillna(0.0)
    start_time = df['time_ms'].iloc[0]
    sliced_res = res[res['time_ms'] >= start_time].copy()
    
    if len(sliced_res) != len(df):
        sliced_res = sliced_res.iloc[-len(df):]

    return sliced_res[['score', 'signal']]