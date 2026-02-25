import pandas as pd
import torch
import torch.nn as nn
import numpy as np
import os
from typing import List, Dict, Any

def description() -> str:
    return "Alpha Gen 1087 - Forensic Interrogator 5.0 (Total Recall Build)"

def meta() -> Dict:
    return {"author": "Gemini", "version": "forensic.5.0.0", "panel": 1, "verified": 1}

def position_args(args: List[str]) -> Dict[str, Any]:
    return {"model-name": args[0] if len(args) > 0 else "model-best-gen22-f1-0.3810.pt"}

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

    # 1. LOAD MODEL & EXTRACT PAYLOAD
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    active_features = checkpoint.get('feature_names', [])
    w1 = checkpoint['W1'].to(device)
    b1 = checkpoint['B1'].to(device).reshape(-1)
    w2 = checkpoint['W2'].to(device)
    b2 = checkpoint['B2'].to(device).reshape(-1)
    means = checkpoint['means'].to(device)
    stds = checkpoint['stds'].to(device)

    # 2. DATA FETCH & ALIGNMENT
    parent_indicators = list(set([f.split(':')[0].split('__')[0] for f in active_features]))
    raw_df = get_data_auto(df, indicators=parent_indicators)
    
    ordered_columns = []
    for f in active_features:
        ordered_columns.append(raw_df[f].values if f in raw_df.columns else np.zeros(len(raw_df)))

    raw_values = np.stack(ordered_columns, axis=1).astype(np.float32)
    raw_model_tensor = torch.from_numpy(raw_values).to(device)

    # 3. NORMALIZATION
    normalized_tensor = (raw_model_tensor - means) / (stds + 1e-8)

    # 4. FULL FEATURE CONTRIBUTION AUDIT
    with torch.no_grad():
        # Contribution = (Input * Weight)
        bar_contribution = normalized_tensor.unsqueeze(2) * w1.unsqueeze(0) 
        feature_impact = bar_contribution.mean(dim=(0, 2)).cpu().numpy()

    # 5. NEURAL INFERENCE
    in_dim, hid_dim = w1.shape
    model = SingularityInference(input_dim=in_dim, hidden_dim=hid_dim).to(device)
    model.l1.weight.data = w1.t()
    model.l1.bias.data = b1
    
    # Check shape of W2 (must be 1, hidden)
    final_w2 = w2 if w2.shape[0] == 1 else w2.t()
    model.l2.weight.data = final_w2
    model.l2.bias.data = b2
    model.eval()

    with torch.no_grad():
        out, h1, a1, s2 = model(normalized_tensor)
        predictions = out.squeeze().cpu().numpy()

    # 6. TOTAL RECALL REPORTING
    print("\n" + "☢️" * 30)
    print(f"TOTAL RECALL FORENSIC AUDIT: {model_name}")
    print(f"Device: {device} | Hidden Dim: {hid_dim}")
    print("-" * 60)
    
    # Feature Table
    header = f"{'FEATURE NAME':<45} | {'RAW MEAN':>10} | {'Z-MEAN':>8} | {'IMPACT':>8}"
    print(header)
    print("-" * 60)
    for i, name in enumerate(active_features):
        r_mean = raw_model_tensor[:, i].mean().item()
        z_mean = normalized_tensor[:, i].mean().item()
        impact = feature_impact[i]
        print(f"{name[:44]:<45} | {r_mean:>10.4f} | {z_mean:>8.4f} | {impact:>8.4f}")

    print("-" * 60)
    print("🧬 [LAYER 2 - THE DEATH ZONE AUDIT]")
    print(f"L2 Bias (b2):             {b2.item():.4f}")
    print(f"L2 Weights (W2) Mean:     {final_w2.mean().item():.4f}")
    print(f"L2 Weights (W2) Max/Min:  {final_w2.max().item():.4f} / {final_w2.min().item():.4f}")
    print(f"Hidden Act (a1) Mean:     {a1.mean().item():.4f} (Sparsity: {(a1 > 0).float().mean().item():.2%})")
    print(f"Pre-Sigmoid (s2) Mean:    {s2.mean().item():.4f}")
    print("-" * 60)
    print(f"FINAL MAX PREDICTION:     {predictions.max():.4f}")
    print("☢️" * 30 + "\n")

    # 7. RETURN
    threshold_val = float(checkpoint.get('threshold', 0.2433))
    full_res = pd.DataFrame(index=raw_df.index)
    full_res['time_ms'] = raw_df['time_ms']
    full_res['score'] = predictions

    full_res['signal'] = np.where(predictions > threshold_val, 1.0, 0.0)

    start_time = df['time_ms'].iloc[0]
    sliced_res = full_res[full_res['time_ms'] >= start_time].copy()
    if len(sliced_res) != len(df):
        sliced_res = sliced_res.iloc[-len(df):]

    return sliced_res[['score', 'signal']]