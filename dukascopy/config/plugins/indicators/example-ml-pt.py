import pandas as pd
import torch
import torch.nn as nn
import numpy as np
import os
import time
from typing import List, Dict, Any

MODEL_REGISTRY = {} 
DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
TTL_SECONDS = 30

def description() -> str:
    return "Alpha Gen 1087 - Forensic Interrogator 5.0 (Performance Audit Build)"

def meta() -> Dict:
    return {"author": "Gemini", "version": "forensic.5.0.4", "panel": 1, "verified": 1}

def position_args(args: List[str]) -> Dict[str, Any]:
    return {"model-name": args[0] if len(args) > 0 else "model-best-gen22-f1-0.3810.pt"}


def warmup_count(options):
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

def get_model_from_registry(checkpoint_path: str):
    now = time.time()
    model_id = os.path.basename(checkpoint_path)
    entry = MODEL_REGISTRY.get(model_id)
    
    if entry:
        if (now - entry['last_load_time']) < TTL_SECONDS:
            return entry['model'], entry['metadata'], False

    if not os.path.exists(checkpoint_path):
        return None, None, False

    checkpoint = torch.load(checkpoint_path, map_location=DEVICE, weights_only=False)
    
    w1 = checkpoint['W1'].to(DEVICE)
    b1 = checkpoint['B1'].to(DEVICE).reshape(-1)
    w2 = checkpoint['W2'].to(DEVICE)
    b2 = checkpoint['B2'].to(DEVICE).reshape(-1)
    
    in_dim, hid_dim = w1.shape
    model = SingularityInference(input_dim=in_dim, hidden_dim=hid_dim).to(DEVICE)
    model.l1.weight.data = w1.t()
    model.l1.bias.data = b1
    model.l2.weight.data = w2 if w2.shape[0] == 1 else w2.t()
    model.l2.bias.data = b2
    model.eval()

    metadata = {
        'feature_names': checkpoint.get('feature_names', []),
        'means': checkpoint['means'].to(DEVICE),
        'stds': checkpoint['stds'].to(DEVICE),
        'threshold': float(checkpoint.get('threshold', 0.2433)),
        'w1': w1 # Keep for impact audit
    }

    MODEL_REGISTRY[model_id] = {
        'model': model,
        'metadata': metadata,
        'last_load_time': now
    }
    
    return model, metadata, True

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    from util.api import get_data_auto

    if df.empty:
        return pd.DataFrame({'score': 0.0, 'signal': 0.0}, index=df.index)
    
    model_name = options.get('model-name', 'model-best-gen22-f1-0.3810.pt')
    checkpoint_path = f"checkpoints/{model_name}"
    
    model, meta_data, did_reload = get_model_from_registry(checkpoint_path)
    
    if model is None:
        return pd.DataFrame({'score': 0.0, 'signal': 0.0}, index=df.index)

    active_features = meta_data['feature_names']
    parent_indicators = list(set([f.split(':')[0].split('__')[0] for f in active_features]))
    raw_df = get_data_auto(df, indicators=parent_indicators + ["is-open"])

    inference_mask = raw_df['is-open'] == 0
    if not inference_mask.any():
        return pd.DataFrame({'score': 0.0, 'signal': 0.0}, index=df.index)

    inf_data = raw_df.loc[inference_mask, active_features].fillna(0.0).values
    raw_model_tensor = torch.from_numpy(inf_data.astype(np.float32)).to(DEVICE)

    with torch.no_grad():
        normalized_tensor = (raw_model_tensor - meta_data['means']) / (meta_data['stds'] + 1e-8)
        out, h1, a1, s2 = model(normalized_tensor)
        predictions = out.view(-1).cpu().numpy()

        if did_reload:
            w1 = meta_data['w1']
            bar_contribution = normalized_tensor.unsqueeze(2) * w1.unsqueeze(0) 
            feature_impact = bar_contribution.mean(dim=(0, 2)).cpu().numpy()
            
            print("\n" + "☢️" * 30)
            print(f"AUDIT REPORT: {model_name} (TTL REFRESH)")
            print(f"Device: {DEVICE} | Buffer: {len(raw_df)} | Mask: {len(raw_model_tensor)}")
            print("-" * 80)
            header = f"{'FEATURE':<50} | {'RAW':>10} | {'Z':>8} | {'IMPACT':>8}"
            print(header)
            print("-" * 80)
            for i, name in enumerate(active_features):
                r_mean = raw_model_tensor[:, i].mean().item()
                z_mean = normalized_tensor[:, i].mean().item()
                imp = feature_impact[i]
                print(f"{name[:49]:<50} | {r_mean:>10.4f} | {z_mean:>8.4f} | {imp:>8.4f}")
            print(f"MAX PREDICTION: {predictions.max():.4f}")
            print("☢️" * 30 + "\n")

    scores = np.zeros(len(raw_df))
    scores[inference_mask] = predictions
    
    result_df = pd.DataFrame({
        'score': scores,
        'signal': (scores > meta_data['threshold']).astype(float)
    }, index=df.index)

    return result_df.ffill().fillna(0.0)