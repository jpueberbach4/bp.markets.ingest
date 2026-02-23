import pandas as pd
import torch
import torch.nn as nn
import numpy as np
import os
from typing import List, Dict, Any

def description() -> str:
    return "Alpha Gen 1087 - Live Inference. Factory Spec 1.3 (Flight Build)"

def meta() -> Dict:
    return {"author": "Gemini", "version": "7-7-7.bar-bar-bar", "panel": 1, "verified": 1}

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
    from ml.space.normalizers.kinematics import Kinematics
    
    model_name = options.get('model-name', 'model-best-gen2-f1-0.1778.pt')
    checkpoint_path = f"checkpoints/{model_name}"

    if not os.path.exists(checkpoint_path):
        return pd.DataFrame({'score': 0.0, 'signal': 0.0}, index=df.index)

    checkpoint = torch.load(checkpoint_path, map_location='cpu', weights_only=False)
    active_features = checkpoint.get('feature_names', [])
    expected_input_dim = checkpoint['W1'].shape[0] 
    actual_hidden_dim = checkpoint['B1'].shape[-1]

    parent_indicators = []
    for f in active_features:
        parent = f.split(':')[0].split('__')[0]
        if parent not in parent_indicators:
            parent_indicators.append(parent)
    
    raw_df = get_data_auto(df, indicators=parent_indicators)

    base_columns = []
    for f in active_features:
        base_col = f.split(':')[0]
        if base_col not in base_columns:
            base_columns.append(base_col)
    
    ordered_matter_df = raw_df.reindex(columns=base_columns).apply(pd.to_numeric, errors='coerce').fillna(0)
    base_tensor = torch.tensor(ordered_matter_df.values.astype(np.float32), dtype=torch.float32)

    redshift = Redshift({})
    kinematics = Kinematics({'filter': {'inclusive': ['*']}}) 
    
    # IMPORTANT!
    # THIS IS AN EXAMPLE WITH ONLY THE REDSHIFT ACTIVE
    # IF YOU USE KINEMATICS, YOU NEED TO SET THE FOLLOWING FLAG TO True.
    # I WILL FIX THIS IN THE FUTURE. NEEDS UNIVERSE NAME IN INPUT AS WELL

    kinematics_disabled = False

    # PRIME THE NORMALIZERS FIRST
    if kinematics_disabled:
        expanded_names = base_columns
    else:
        # This populates self.eligible_indices inside the class!
        expanded_names = kinematics.generate_names(base_columns)

    # EXECUTE THE PHYSICS
    with torch.no_grad():
        if kinematics_disabled:
            expanded_tensor = base_tensor
        else:
            expanded_tensor = kinematics.forward(base_tensor)

        normalized_tensor = redshift.forward(expanded_tensor)
        
    name_to_idx = {name: i for i, name in enumerate(expanded_names)}
    
    indices = []
    for f in active_features:
        if f in name_to_idx:
            indices.append(name_to_idx[f])
        else:
            naked_fallback = f"{f}:dir"
            if naked_fallback in name_to_idx:
                indices.append(name_to_idx[naked_fallback])
            else:
                print(f"💀 [Inference]: Feature {f} is completely unreachable.")
                return pd.DataFrame({'score': 0.0, 'signal': 0.0}, index=df.index)

    final_tensor = normalized_tensor[:, indices]

    model = SingularityInference(input_dim=expected_input_dim, hidden_dim=actual_hidden_dim)
    model.load_state_dict({
        'l1.weight': checkpoint['W1'].t(), 'l1.bias': checkpoint['B1'].reshape(-1),
        'l2.weight': checkpoint['W2'].t(), 'l2.bias': checkpoint['B2'].reshape(-1)
    })
    model.eval()

    with torch.no_grad():
        predictions = model(final_tensor).squeeze().cpu().numpy()

    raw_thresh = checkpoint.get('threshold', 0.40)
    threshold_val = float(raw_thresh.item()) if torch.is_tensor(raw_thresh) else float(raw_thresh)

    res = pd.DataFrame(index=df.index)
    res['score'] = predictions
    res['signal'] = np.where(predictions > threshold_val, 1.0, 0.0)
    
    return res