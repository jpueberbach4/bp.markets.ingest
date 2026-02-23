import pandas as pd
import torch
import torch.nn as nn
import numpy as np
import os
from typing import List, Dict, Any

def description() -> str:
    return "Alpha Gen 1087 - Live Inference. Factory Spec 1.3 (Flight Build)"

def meta() -> Dict:
    return {"author": "Gemini", "version": "33.3_ATOMIC_STABILITY", "panel": 1, "verified": 1}

def position_args(args: List[str]) -> Dict[str, Any]:
    return {"model-name": args[0] if len(args) > 0 else "model-best-gen14-f1-0.3636.pt"}

def warmup_count(options: Dict[str, Any]):
    return 1000

class SingularityInference(nn.Module):
    """
    Adaptive architecture. Hidden dimension is determined at runtime 
    based on the Hale-Bopp checkpoint payload.
    """
    def __init__(self, input_dim: int, hidden_dim: int):
        super(SingularityInference, self).__init__()
        self.l1 = nn.Linear(input_dim, hidden_dim)
        self.l2 = nn.Linear(hidden_dim, 1)
        self.activation = nn.GELU() 
        self.out_act = nn.Sigmoid()
        
    def forward(self, x):
        x = self.activation(self.l1(x))
        x = self.out_act(self.l2(x))
        return x

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    from util.api import get_data_auto
    from ml.space.normalizers.redshift import Redshift
    
    model_name = options.get('model-name', 'model-best-gen14-f1-0.3636.pt')
    checkpoint_path = f"checkpoints/{model_name}"

    if not os.path.exists(checkpoint_path):
        print(f"🚨 [Inference]: Model missing: {checkpoint_path}")
        return pd.DataFrame({'score': 0.0, 'signal': 0.0}, index=df.index)

    # Load with False weights_only to allow full state dict parsing
    checkpoint = torch.load(checkpoint_path, map_location='cpu', weights_only=False)
    active_features = checkpoint.get('feature_names', [])
    
    # DYNAMIC DIMENSION DETECTION
    if 'hidden_dim' in checkpoint:
        actual_hidden_dim = checkpoint['hidden_dim']
    else:
        # If metadata is missing, we infer it from the B1 bias or W1 weights
        actual_hidden_dim = checkpoint['B1'].shape[-1]
        print(f"📡 [Inference]: Inferred hidden_dim: {actual_hidden_dim}")

    base_indicators = list(set([f.split('__')[0] for f in active_features]))
    raw_df = get_data_auto(df, indicators=base_indicators)
    
    selected_features_df = raw_df[active_features].apply(pd.to_numeric, errors='coerce').fillna(0)
    input_array = selected_features_df.values.astype(np.float32)
    data_tensor = torch.tensor(input_array)
    
    normalizer = Redshift()
    with torch.no_grad():
        normalized_tensor = normalizer(data_tensor)
    
    # Initialize model with the detected dimension
    model = SingularityInference(input_dim=len(active_features), hidden_dim=actual_hidden_dim)
    
    try:
        model.load_state_dict({
            'l1.weight': checkpoint['W1'].t(),
            'l1.bias': checkpoint['B1'].reshape(-1),
            'l2.weight': checkpoint['W2'].t(),
            'l2.bias': checkpoint['B2'].reshape(-1)
        })
    except RuntimeError as e:
        print(f"💀 [Inference]: Critical structural mismatch: {e}")
        return pd.DataFrame({'score': 0.0, 'signal': 0.0}, index=df.index)

    model.eval()

    with torch.no_grad():
        predictions = model(normalized_tensor).squeeze().cpu().numpy()

    res = pd.DataFrame(index=df.index)
    res['score'] = predictions
    
    threshold_val = checkpoint.get('threshold', 0.40)
    if torch.is_tensor(threshold_val):
        threshold_val = threshold_val.item()
    
    res['signal'] = np.where(predictions > threshold_val, 1.0, 0.0)
    return res