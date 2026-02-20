import pandas as pd
import torch
import numpy as np
from typing import List, Dict, Any

def description() -> str:
    return (
        "Alpha Gen 117 - High Visibility. Scales the binary signal to the "
        "max observed score to ensure it is visible against wide-range scores."
    )

def meta() -> Dict:
    return {
        "author": "Google Gemini",
        "version": 1.21,
        "panel": 1,  # Sub-panel 1
        "verified": 1,
        "polars": 0
    }

def warmup_count(options: Dict[str, Any]) -> int:
    return 150 

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    """
    Neural Inference with Visibility Scaling.
    The signal is multiplied by the max score to create visible 'spikes'.
    """
    from util.api import get_data_auto
    import os

    # Load Checkpoint
    ckpt_path = 'checkpoints/best_model_gen_117.pt'
    if not os.path.exists(ckpt_path):
        ckpt_path = 'best_model_gen_117.pt'

    ckpt = torch.load(ckpt_path, map_location='cpu', weights_only=True)
    genes = ckpt['genes']
    state = ckpt['state_dict']
    
    # Fetch Data
    base_indicators = sorted(list(set([g.split('__')[0] for g in genes])))
    ex_df = get_data_auto(df, indicators=base_indicators)
    
    # Sanitization (Ingestion Parity)
    try:
        feature_slice = ex_df[genes].copy()
        feature_slice = feature_slice.apply(pd.to_numeric, errors='coerce').fillna(0.0)
        clean_numpy = feature_slice.to_numpy(dtype=np.float32)
        input_tensor = torch.from_numpy(clean_numpy)
    except Exception as e:
        return pd.DataFrame(index=df.index, data={'alpha_score': 0, 'alpha_signal': 0})

    # Neural Inference
    with torch.no_grad():
        w1, b1 = state['W1'].cpu(), state['B1'].cpu()
        w2, b2 = state['W2'].cpu(), state['B2'].cpu()
        threshold = state['threshold'].cpu().item()

        # Interaction Layer
        hidden = torch.nn.functional.relu(torch.matmul(input_tensor, w1) + b1)
        
        # Scoring
        scores_tensor = torch.matmul(hidden, w2) + b2
        
        # Binary Trigger
        signals_tensor = (scores_tensor > threshold).float()
    
    # Visibility Logic: Scale Signal to Max Score
    # Convert back to numpy
    scores = scores_tensor.numpy().flatten()
    signals = signals_tensor.numpy().flatten()
    
    # Find the maximum score in the visible range to act as our 'Ceiling'
    max_visible_score = np.max(scores) if len(scores) > 0 else 1.0
    
    # If max is negative or zero, use a default positive constant to ensure visibility
    signal_height = max_visible_score if max_visible_score > 0 else 100.0

    # Assembly
    res = pd.DataFrame(index=df.index)
    res['alpha_score'] = scores
    
    # We multiply the 0/1 by the height so it spikes to the top of the pane
    res['alpha_signal'] = signals * 2000
    
    return res[['alpha_score', 'alpha_signal']]