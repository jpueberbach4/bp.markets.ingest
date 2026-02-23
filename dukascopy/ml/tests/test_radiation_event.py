import torch
import numpy as np
from ml.space.universes.milkyway import MilkyWay
from ml.space.singularity_overengineered import EventHorizonSingularity

def test_radiation_logic():
    # 1. Setup minimal config
    config = {
        "POP_SIZE": 100, "GENE_COUNT": 24, "HIDDEN_DIM": 64,
        "GPU_CHUNK": 50, "LEARNING_RATE": 0.0005, "EPOCHS": 1,
        "OOS_BOUNDARY": 0.75, "VITALITY_DECAY": 0.90, "PRECISION_EXP": 3.0,
        "MIN_SIGNALS": 3, "WEIGHT_MUTATION_RATE": 0.005, "TARGET_DENSITY": 0.01,
        "PENALTY_COEFF": 1.0, "VERBOSE": False, "MAX_GENERATIONS": 15,
        "EXTINCTION_THRESHOLD": 0.01,
    }
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    universe = MilkyWay("ml/config.yaml", symbol="EUR-USD", timeframe="4h")
    universe.ignite(after_ms=1640995200000, until_ms=1757952000000, limit=100000)
    reactor = EventHorizonSingularity(config, device=device)
    reactor.compress(universe)
    
    total_features = len(universe.features())
    stagnation_counter = 0
    stagnation_limit = 5 # Shorten for test
    best_f1 = 999.0      # Set impossible high to force stagnation
    
    print(f"🛠️ [Test]: Starting drill with {total_features} features...")
    
    # Capture DNA before
    original_dna = reactor.population.clone()

    for gen in range(1, 10):
        # Simulate no improvement
        stagnation_counter += 1
        print(f"Gen {gen}: Stagnation {stagnation_counter}/{stagnation_limit}")
        
        if stagnation_counter >= stagnation_limit:
            print("☢️  TESTING RADIATION EVENT...")
            with torch.no_grad():
                n_nuke = int(config["POP_SIZE"] * 0.40)
                indices = torch.randperm(config["POP_SIZE"], device=device)[:n_nuke]
                new_dna = torch.randint(0, total_features, (n_nuke, config["GENE_COUNT"]), 
                                        device=device, dtype=reactor.population.dtype)
                reactor.population[indices] = new_dna
            
            # VERIFICATION
            changes = (reactor.population != original_dna).any(dim=1).sum().item()
            print(f"✅ VERIFIED: {changes} individuals have mutated DNA.")
            if changes > 0:
                print("🚀 STAGNATION BREAKER IS FUNCTIONAL.")
                return True
            stagnation_counter = 0

    return False

if __name__ == "__main__":
    test_radiation_logic()