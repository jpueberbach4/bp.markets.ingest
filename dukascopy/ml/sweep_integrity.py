import torch
import pandas as pd
import numpy as np
from reactor import PersistentReactor
from ingest import IndicatorIngestor

from main import CONFIG

def run_final_sweep(checkpoint_file):
    global CONFIG
    print(f"🚀 [Triple Threat] Final Integrity Sweep: {checkpoint_file}")
    
    # 1. Setup Device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    # 2. Load the Saved State
    try:
        ckpt = torch.load(checkpoint_file)
        print(f"✅ Loaded Gen {ckpt['gen']} | Target F1: {ckpt['f1']:.4f}")
    except Exception as e:
        print(f"❌ Load Error: {e}"); return

    # 3. Use your existing CONFIG from main.py
    from main import CONFIG 
    
    # 4. Ingest Fresh Data (Ensures no caching bias)
    ingestor = IndicatorIngestor(CONFIG)
    features, targets, _ = ingestor.get_data()
    
    # 5. Initialize a 'Clean' Reactor
    reactor = PersistentReactor(features, targets, CONFIG, device)
    
    # 6. Inject the Gen 19 DNA
    with torch.no_grad():
        gene_indices = [features.columns.get_loc(g) for g in ckpt['genes']]
        reactor.population[0] = torch.tensor(gene_indices, device=device).long()
        reactor.pop_W1[0].copy_(ckpt['state_dict']['W1'].to(device))
        reactor.pop_W2[0].copy_(ckpt['state_dict']['W2'].to(device))
        reactor.pop_B1[0].copy_(ckpt['state_dict']['B1'].to(device))
        reactor.pop_B2[0].copy_(ckpt['state_dict']['B2'].to(device))
        reactor.thresholds[0].copy_(ckpt['state_dict']['threshold'].to(device))

    # 7. Execute Validation Flight
    print("🛰️ Running Validation Flight...")
    metrics = reactor.run_generation()
    
    val_f1 = metrics['f1'][0].item()
    val_sigs = metrics['sigs'][0].item()
    
    print(f"\n" + "="*40)
    print(f"ORIGINAL F1: {ckpt['f1']:.4f}")
    print(f"VALIDATED F1: {val_f1:.4f}")
    print(f"SIGNALS: {val_sigs}")
    print("="*40)

    if abs(ckpt['f1'] - val_f1) < 1e-6:
        print("💎 RESULT: 100% BIT-INTEGRITY. Baseline is Solid.")
    else:
        print("⚠️ RESULT: Bit-Drift Detected. Check GPU Thermals.")

if __name__ == "__main__":
    run_final_sweep("checkpoints/best_model_gen_3.pt")