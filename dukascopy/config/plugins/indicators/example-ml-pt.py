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

    kinematics = Kinematics({'filter': {'inclusive': ['*']}})

    # NOTE! WHEN YOU DONT USE KINEMATICS, DISABLE IT HERE 
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

    name_to_idx = {name: i for i, name in enumerate(expanded_names)}
    
    # SPEC TENSOR ASSEMBLY
    raw_model_columns = []
    for f in active_features:
        if f in name_to_idx:
            # Kinematics processed and kept the feature
            raw_model_columns.append(expanded_tensor[:, name_to_idx[f]])
        elif f in base_columns:
            # Kinematics dropped the base feature; rescue it directly from the source tensor
            base_idx = base_columns.index(f)
            raw_model_columns.append(base_tensor[:, base_idx])
        else:
            # Absolute last resort fallback
            naked_fallback = f"{f}:dir"
            if naked_fallback in name_to_idx:
                print(f"⚠️ [Warning]: Silent fallback triggered for {f} -> {naked_fallback}")
                raw_model_columns.append(expanded_tensor[:, name_to_idx[naked_fallback]])
            else:
                print(f"💀 [Inference]: Feature {f} is completely unreachable.")
                return pd.DataFrame({'score': 0.0, 'signal': 0.0}, index=df.index)

    # Stack the exact raw features the model expects
    raw_model_tensor = torch.stack(raw_model_columns, dim=1)

    # Apply the exact Global Scale from the training checkpoint
    if 'means' in checkpoint and 'stds' in checkpoint:
        saved_means = checkpoint['means'].to(raw_model_tensor.device)
        saved_stds = checkpoint['stds'].to(raw_model_tensor.device)
        final_tensor = (raw_model_tensor - saved_means) / (saved_stds + 1e-8)
        global_scaling_applied = True
    else:
        # Fallback to pure local scaling
        final_tensor = (raw_model_tensor - raw_model_tensor.mean(dim=0)) / (raw_model_tensor.std(dim=0) + 1e-8)
        global_scaling_applied = False


    # --- INFERENCE DIAGNOSTIC ---
    print("\n" + "="*40)
    print("🔍 [Inference Audit]")
    zero_cols = (ordered_matter_df == 0).all(axis=0)
    if zero_cols.any():
        print(f"⚠️ DANGER: {zero_cols.sum()} features are entirely ZERO (Missing Data).")
        print(f"Empty Columns: {zero_cols[zero_cols].index.tolist()}")
    
    print(f"Final Tensor Min: {final_tensor.min().item():.4f} | Max: {final_tensor.max().item():.4f}")
    if global_scaling_applied:
        print("✅ Global Scaling (Factory Specs) Applied.")
    else:
        print("❌ Local Scaling Applied (Model lacks saved physics).")
    print("="*40 + "\n")


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