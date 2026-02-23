import torch
import numpy as np
import pandas as pd
from ingest import IndicatorIngestor
from reactor import PersistentReactor
from config import CONFIG

def validate_factory_spec(X_df, checkpoint, device):
    state = checkpoint['state_dict']
    gene_names = checkpoint['genes']
    
    # 1. LOAD WEIGHTS (Strictly using the UPPERCASE keys from your .pt)
    W1 = state['W1'].to(device) # Shape: [Genes, Hidden]
    B1 = state['B1'].to(device) # Shape: [1, Hidden]
    W2 = state['W2'].to(device) # Shape: [Hidden, 1]
    B2 = state['B2'].to(device) # Shape: [1, 1]

    # 2. SELECT GENES
    # We must slice the dataframe to ONLY the indicators the model knows
    X_sliced = X_df[gene_names].values
    X_tensor = torch.tensor(np.nan_to_num(X_sliced.astype(np.float32))).to(device)

    # 3. THE NEURAL PASS (Standardized to match Reactor forward logic)
    # Layer 1: Linear + LeakyReLU
    # (Batch x Genes) @ (Genes x Hidden) + B1
    h1 = torch.matmul(X_tensor, W1) + B1
    h1 = torch.nn.functional.leaky_relu(h1, 0.1)

    # Layer 2: Linear + Sigmoid
    # (Batch x Hidden) @ (Hidden x 1) + B2
    logits = torch.matmul(h1, W2) + B2
    probs = torch.sigmoid(logits)

    return probs.squeeze()

def run_sanity_check():
    # Load Training Data (Ground Truth)
    print("⏳ Loading Training Set for Baseline Check...")
    ingestor = IndicatorIngestor(CONFIG)
    X_train, y_train, _ = ingestor.get_data()
    
    # Load the Model
    checkpoint = torch.load("checkpoints/best_model_gen_65.pt", map_location=CONFIG['DEVICE'])
    
    with torch.no_grad():
        probs = validate_factory_spec(X_train, checkpoint, CONFIG['DEVICE'])
        # Use 0.7 threshold from factory specs
        preds = (probs > 0.7).cpu().numpy().astype(int)
        
    # Validation
    y_true = y_train.values.astype(int)
    matches = (preds == y_true).sum()
    acc = matches / len(y_true)
    
    tp = ((y_true == 1) & (preds == 1)).sum()
    fp = ((y_true == 0) & (preds == 1)).sum()

    print("\n" + "="*40)
    print(f"🏠 TRAINING SET INTERNAL CHECK")
    print(f"Accuracy:  {acc:.4f}")
    print(f"Hits (TP): {tp}")
    print(f"Misfires:  {fp}")
    print("="*40)

if __name__ == "__main__":
    run_sanity_check()