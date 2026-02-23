import os
import torch
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg') # Force non-interactive backend
import matplotlib.pyplot as plt

from ingest import IndicatorIngestor
from features import apply_temporal_universe  # Crucial for feature alignment
from config import CONFIG

# --- AUDIT CONFIG ---
CHECKPOINT_PATH = "checkpoints/best_model_gen_1087.pt"
ITERATIONS = 1000  
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

def load_specialist_model(checkpoint_path):
    """Loads weights and the specific gene list from the checkpoint."""
    ckpt = torch.load(checkpoint_path, map_location=DEVICE, weights_only=True)
    state = ckpt['state_dict']
    genes = ckpt['genes']
    
    def model_fn(x):
        # Hidden Layer 1 with Leaky ReLU (matching Reactor's _forward logic)
        h = torch.nn.functional.leaky_relu(x @ state['W1'].to(DEVICE) + state['B1'].to(DEVICE), 0.1)
        # Output Layer
        logits = h @ state['W2'].to(DEVICE) + state['B2'].to(DEVICE)
        return logits

    return model_fn, ckpt['f1'], genes, ckpt.get('threshold', 0.7)

def run_rigorous_audit():
    print(f"🚀 Initializing Audit for: {CHECKPOINT_PATH}")
    
    # 1. Ingest Base Data
    ingestor = IndicatorIngestor(CONFIG)
    base_feats_df, targets_df, _ = ingestor.get_data() 

    # 2. Apply Temporal Universe (Expansion to dt1, dt3)
    # This ensures genes like 'volatility_dt1' exist in our dataframe
    print("🌌 Expanding Temporal Universe...")
    feats_expanded_df = apply_temporal_universe(base_feats_df)
    
    # 3. Load Model and Gene List
    model, baseline_f1, active_genes, saved_threshold = load_specialist_model(CHECKPOINT_PATH)
    print(f"✅ Model Loaded. Target Genes: {len(active_genes)}")

    # 4. Feature Alignment & Tensor Conversion
    try:
        # Filter the expanded 300+ column universe to ONLY the 24 genes the model expects
        feats_filtered = feats_expanded_df[active_genes]
    except KeyError as e:
        print(f"❌ Feature Mismatch: The following genes are missing from the expanded universe: {e}")
        print("Check if apply_temporal_universe logic has changed since training.")
        return

    # Convert to Tensors
    # Using nan_to_num to prevent 'NaN' from breaking the matrix multiplication
    feats_vals = np.nan_to_num(feats_filtered.values.astype(np.float32))
    feats = torch.tensor(feats_vals, device=DEVICE)
    targets = torch.tensor(targets_df.values.astype(np.float32), device=DEVICE)
    
    print(f"✅ Data Aligned. Tensor Shape: {feats.shape}")

    # 5. Baseline Inference
    with torch.no_grad():
        logits = model(feats)
        probs = torch.sigmoid(logits)
        # Use the specific threshold that Gen 1087 was optimized for
        preds = (probs > saved_threshold).float()
        
        actual_sigs = preds.sum().item()
        actual_tp = (preds * targets).sum().item()
        actual_fp = (preds * (1 - targets)).sum().item()
        actual_fn = ((1 - preds) * targets).sum().item()
        
        actual_prec = actual_tp / (actual_tp + actual_fp + 1e-8)
        actual_rec = actual_tp / (actual_tp + actual_fn + 1e-8)


    # Calculate Weighted F1 to match Reactor's 'Factory Specs'
    prec_exp = 6
    denom = actual_prec + actual_rec
    weighted_f1 = (2 * (actual_prec**prec_exp * actual_rec)) / (denom + 1e-8)

    print(f"Heuristic F1 (Factory): {weighted_f1:.4f}")
    print(f"Raw Precision:          {actual_prec:.4f}")

    # --- TEST 1: MONTE CARLO PERMUTATION ---
    print(f"🔬 Running {ITERATIONS} Permutations...")
    null_f1s = []
    
    for i in range(ITERATIONS):
        y_shuffled = targets[torch.randperm(targets.size(0))]
        
        tp = (preds * y_shuffled).sum().item()
        fp = (preds * (1 - y_shuffled)).sum().item()
        fn = ((1 - preds) * y_shuffled).sum().item()
        
        f1 = (2 * tp) / (2 * tp + fp + fn + 1e-8)
        null_f1s.append(f1)
        
        if (i+1) % 250 == 0:
            print(f"   [Progress] {i+1}/{ITERATIONS} iterations complete.")

    p_value = np.sum(np.array(null_f1s) >= baseline_f1) / ITERATIONS

    # --- TEST 2: FRICTION SENSITIVITY ---
    costs = [0, 0.5, 1.0, 1.5, 2.0, 3.0] 
    decayed_f1s = [baseline_f1 * max(0, 1.0 - (c * 0.15)) for c in costs]

    # --- FINAL REPORT ---
    print("\n" + "="*50)
    print(f"{'AUDIT REPORT: GEN 1087':^50}")
    print("="*50)
    print(f"SIGNIFICANCE: {'✅ PASS' if p_value < 0.01 else '❌ FAIL'}")
    print(f"P-Value:      {p_value:.6f}")
    print(f"Baseline F1:  {baseline_f1:.4f}")
    print(f"Threshold:    {saved_threshold:.4f}")
    print(f"Signals:      {int(actual_sigs)}")
    print(f"Precision:    {actual_prec:.4f}")
    print(f"Recall:       {actual_rec:.4f}")
    print("-" * 50)
    
    if p_value < 0.01:
        print("ANALYSIS: Statistically robust. Edge is likely real.")
    else:
        print("ANALYSIS: Failed significance. Likely curve-fitting/noise.")

    # --- VISUALIZATION ---
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    ax1.hist(null_f1s, bins=40, color='gray', alpha=0.6, label='Null Hypothesis')
    ax1.axvline(baseline_f1, color='red', linestyle='--', label='Gen 1087 Performance')
    ax1.set_title("Monte Carlo: Significance Test")
    ax1.set_xlabel("F1 Score")
    ax1.legend()

    ax2.plot(costs, decayed_f1s, marker='o', color='blue', linewidth=2)
    ax2.axhline(0.10, color='red', linestyle=':', label='Viability Floor')
    ax2.set_title("Slippage Sensitivity (Alpha Decay)")
    ax2.set_xlabel("Pips")
    ax2.set_ylabel("Simulated F1")
    ax2.grid(True, alpha=0.3)
    ax2.legend()
    
    plt.tight_layout()
    plt.savefig('logs/audit_report_1087.png')
    print("📊 Report saved as audit_report_1087.png")

if __name__ == "__main__":
    run_rigorous_audit()