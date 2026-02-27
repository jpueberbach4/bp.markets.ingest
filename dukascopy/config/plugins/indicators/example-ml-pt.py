import pandas as pd
import torch
import torch.nn as nn
import numpy as np
import os
from typing import List, Dict, Any

def description() -> str:
    return (
        "High-fidelity inference engine utilizing a Registry-Cached Singularity architecture. "
        "Implements strict 'is-open' data isolation and 'merge_asof' backward alignment to "
        "eliminate look-ahead bias and repainting. Provides real-time feature impact audits "
        "and normalized Z-score telemetry for live model verification. Audits of unique models "
        "are performed every 30 seconds. See your console for more information."
    )
            

def meta() -> Dict:
    return {"author": "JP", "version": "2.0.0", "panel": 1, "verified": 1}

def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "model-name": args[0] if len(args) > 0 else "model-best-gen22-f1-0.3810.pt",
        "threshold": args[1] if len(args) > 1 else 0.2433

    }

def warmup_count(args: List[str]) -> Dict[str, Any]:
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

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    from util.api import get_data_auto
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model_name = options.get('model-name', 'model-best-gen22-f1-0.3810.pt')
    checkpoint_path = f"checkpoints/{model_name}"

    if not os.path.exists(checkpoint_path):
        return pd.DataFrame({'score': 0.0, 'signal': 0.0}, index=df.index)

    # Load model
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    active_features = checkpoint.get('feature_names', [])
    w1 = checkpoint['W1'].to(device)
    b1 = checkpoint['B1'].to(device).reshape(-1)
    w2 = checkpoint['W2'].to(device)
    b2 = checkpoint['B2'].to(device).reshape(-1)
    means = checkpoint['means'].to(device)
    stds = checkpoint['stds'].to(device)

    parent_indicators = list(set([f.split(':')[0].split('__')[0] for f in active_features]))

    raw_df = get_data_auto(df, indicators=parent_indicators + ["is-open"])

    inference_df = raw_df[raw_df['is-open'] == 0].copy()
    
    if inference_df.empty:
         return pd.DataFrame({'score': 0.0, 'signal': 0.0}, index=df.index)

    ordered_columns = []
    for f in active_features:
        ordered_columns.append(inference_df[f].values if f in inference_df.columns else np.zeros(len(inference_df)))

    raw_values = np.stack(ordered_columns, axis=1).astype(np.float32)
    raw_model_tensor = torch.from_numpy(raw_values).to(device)

    normalized_tensor = (raw_model_tensor - means) / (stds + 1e-8)

    with torch.no_grad():
        bar_contribution = normalized_tensor.unsqueeze(2) * w1.unsqueeze(0) 
        feature_impact = bar_contribution.mean(dim=(0, 2)).cpu().numpy()

    in_dim, hid_dim = w1.shape
    model = SingularityInference(input_dim=in_dim, hidden_dim=hid_dim).to(device)
    model.l1.weight.data = w1.t()
    model.l1.bias.data = b1
    
    final_w2 = w2 if w2.shape[0] == 1 else w2.t()
    model.l2.weight.data = final_w2
    model.l2.bias.data = b2
    model.eval()

    with torch.no_grad():
        out, h1, a1, s2 = model(normalized_tensor)
        predictions = out.squeeze().cpu().numpy()
        if predictions.ndim == 0:
            predictions = np.array([predictions.item()])

    print("\n" + "☢️" * 60)
    print(f"STABLE AS-OF AUDIT: {model_name}")
    print(f"Device: {device} | Total Bars: {len(raw_df)} | Inference Bars: {len(inference_df)}")
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

    threshold_val = float(options.get('threshold', 0.2433))

    stable_results = pd.DataFrame({
        'time_ms': inference_df['time_ms'],
        'score': predictions
    })
    stable_results['signal'] = np.where(stable_results['score'] > threshold_val, 1.0, 0.0)

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