import torch
import pandas as pd
import numpy as np

def perform_forensic_pass(checkpoint_path):
    print(f"--- Forensic Analysis of {checkpoint_path} ---")
    
    # 1. Load the "Evolved Soul"
    try:
        data = torch.load(checkpoint_path, map_location='cpu')
    except Exception as e:
        print(f"Error loading checkpoint: {e}")
        return

    genes = data.get('genes', [])
    state_dict = data.get('state_dict', {})
    
    # 2. Extract the Weights
    # W1 shape is [12, 128] -> [Input_Genes, Hidden_Layer]
    W1 = state_dict.get('W1').numpy()
    
    # 3. Calculate Feature Importance
    # We sum the absolute weights of all connections from each gene to the hidden layer
    # This shows how much "influence" each gene has on the brain's decision.
    importance = np.sum(np.abs(W1), axis=1)
    
    # 4. Create a clean report
    report = pd.DataFrame({
        'Gene': genes,
        'Importance_Score': importance
    }).sort_values(by='Importance_Score', ascending=False)
    
    # Normalize importance for readability (0-100)
    report['Relative_Weight_%'] = (report['Importance_Score'] / report['Importance_Score'].sum()) * 100
    
    print(f"Generation: {data.get('gen', 'Unknown')}")
    print(f"Target F1: {data.get('f1', 'Unknown'):.4f}")
    print("\n--- Logic Map (Feature Importance) ---")
    print(report[['Gene', 'Relative_Weight_%']].to_string(index=False))
    
    # 5. Extract Threshold Logic
    threshold = state_dict.get('threshold').item()
    print(f"\nTrigger Threshold: {threshold:.4f}")
    print("-" * 40)

if __name__ == "__main__":
    # Run this on your best model (e.g., gen_372.pt or gen_156.pt)
    perform_forensic_pass('checkpoints/best_model_gen_156.pt')