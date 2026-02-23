import pandas as pd
import torch
import torch.nn as nn
import numpy as np
import os
from typing import List, Dict, Any

def description() -> str:
    return "Alpha Gen 1087 - Live Inference. Factory Spec 1.3 (Flight Build)"

def meta() -> Dict:
    return {"author": "Gemini", "version": "33.2_ATOMIC_STABILITY", "panel": 1, "verified": 1}

def position_args(args: List[str]) -> Dict[str, Any]:
    return {"model-name": args[0] if len(args) > 0 else "model_best_gen14_f1_0.3636.pt"}

def warmup_count(options: Dict[str, Any]):
    return 1000


class SingularityInference(nn.Module):
    """
    Architecture synced to Factory Spec 1.3: HIDDEN_DIM = 256
    Uses GELU activation to match EventHorizonSingularity._forward exactly.
    """
    def __init__(self, input_dim: int, hidden_dim: int = 256):
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
    
    model_name = options.get('model-name', 'model_best_gen14_f1_0.3636.pt')

    checkpoint_path = f"checkpoints/{model_name}"
    if not os.path.exists(checkpoint_path):
        return pd.DataFrame({'alpha_score': 0.0, 'alpha_signal': 0.0}, index=df.index)

    checkpoint = torch.load(checkpoint_path, map_location='cpu', weights_only=False)
    active_features = checkpoint.get('feature_names', [])
    
    base_indicators = list(set([f.split('__')[0] for f in active_features]))
    raw_df = get_data_auto(df, indicators=base_indicators)
    
    # Force alignment and numeric conversion immediately
    selected_features_df = raw_df[active_features].apply(pd.to_numeric, errors='coerce').fillna(0)
    
    # Fix: Ensure the numpy array is purely float before tensor conversion
    input_array = selected_features_df.values.astype(np.float32)
    data_tensor = torch.tensor(input_array)
    
    normalizer = Redshift()
    with torch.no_grad():
        normalized_tensor = normalizer(data_tensor)
    
    model = SingularityInference(input_dim=len(active_features), hidden_dim=256)
    model.load_state_dict({
        'l1.weight': checkpoint['W1'].t(),
        'l1.bias': checkpoint['B1'].reshape(-1),
        'l2.weight': checkpoint['W2'].t(),
        'l2.bias': checkpoint['B2'].reshape(-1)
    })
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