import torch
import numpy as np
import pandas as pd
import time
from datetime import datetime
import sys
from ml.space.universes.milkyway import MilkyWay
from ml.space.singularity import EventHorizonSingularity

def run_test_flight():
     config = {
          'START_DATE': '2022-01-01',
          'END_DATE': '2025-12-31',
          "POP_SIZE": 1200,
          "GENE_COUNT": 12,
          "HIDDEN_DIM": 256,
          "GPU_CHUNK": 200,
          "LEARNING_RATE": 0.0005,
          "EPOCHS": 15,
          "OOS_BOUNDARY": 0.75,
          "VITALITY_DECAY": 0.90,
          "PRECISION_EXP": 1.5,
          "MIN_SIGNALS": 5,
          "WEIGHT_MUTATION_RATE": 0.005,
          "TARGET_DENSITY": 0.01,
          "PENALTY_COEFF": 50.0,
          "VERBOSE": True,
          "MAX_GENERATIONS": 5000,
          "EXTINCTION_THRESHOLD": 0.01,
          'EXTINCTION_STAGNATION': 60,
          'RADIATION_STAGNATION': 30,
          'HOTNESS_MAX': 87,
          'HOTNESS_MIN': 80,
          "TARGET_DENSITY": 0.01,
          "PENALTY_COEFF": 1.0,
          "THRESH_STEPS": 31,
          "EMA_ALPHA": 0.1,
          "W1_MUTATION_RATE": 0.02,    # Was 0.005 (4x increase)
          "W2_MUTATION_RATE": 0.002,    # Was 0.0005 (4x increase)
     }
     
     after_dt = datetime.fromisoformat(config['START_DATE'])
     until_dt = datetime.fromisoformat(config['END_DATE'])

     after_ms = int(after_dt.timestamp() * 1000)
     until_ms = int(until_dt.timestamp() * 1000)

     print(f"🌌 [Flight]: Initializing MilkyWay Universe... {after_ms} -> {until_ms}")
     universe = MilkyWay("ml/config.yaml", symbol="EUR-USD", timeframe="4h")
     universe.ignite(after_ms=after_ms, until_ms=until_ms, limit=1000000)
     
     device = "cuda" if torch.cuda.is_available() else "cpu"
     reactor = EventHorizonSingularity(config, device=device)
     
     print("🕳️ [Flight]: Compressing universe into the Singularity...")
     reactor.compress(universe)
     
     best_f1 = -1.0
     best_gen = 0
     stagnation_counter = 0
     stagnation_limit = config['RADIATION_STAGNATION'] 
     extinction_limit = config['EXTINCTION_STAGNATION']
     hotness_max = config['HOTNESS_MAX'] 
     hotness_min = config['HOTNESS_MIN']
     
     # Get the total number of features available in this universe
     total_features = len(universe.features())
     
     generations = config['MAX_GENERATIONS']  
     for gen in range(1, generations + 1):
          print(f"\n" + "="*60)
          print(f"🚀 [Flight]: Commencing Generation {gen}/{generations}")
          print("="*60)
          
          start_t = time.time()
          metrics = reactor.run_generation(universe)
          duration = time.time() - start_t
          
          fitness = metrics["score"]
          avg_f1 = metrics["f1"].mean().item()
          max_f1 = metrics["f1"].max().item()
          avg_prec = metrics["precision"].mean().item()
          max_prec = metrics["precision"].max().item()
          total_sigs = metrics["sigs"].sum().item()
          
          print(f"\n📊 [Gen {gen} Summary] ({duration:.1f}s)")
          print(f"   F1:         Avg {avg_f1:.4f} | Max {max_f1:.4f}")
          print(f"   Precision: Avg {avg_prec:.4f} | Max {max_prec:.4f}")
          print(f"   Activity:  Total Sigs {int(total_sigs)} | Density {metrics['density'].mean().item():.4%}")

          if max_f1 > best_f1:
              print(f"🏆 [Flight]: New High Water Mark! {max_f1:.4f} beats {best_f1:.4f}")
              best_f1 = max_f1
              best_gen = gen
              stagnation_counter = 0 
              
              # CRITICAL: We find the specific index of the individual achieving max_f1
              winner_idx = torch.argmax(fitness).item()
              filename = f"model-best-gen{gen}-f1-{max_f1:.4f}.pt"
              
              # Save only the winner's specific state for inference stability
              reactor.save_state(universe, filename, winner_idx=winner_idx)
          else:
              stagnation_counter += 1
              print(f"📉 [Flight]: No improvement. Stagnation: {stagnation_counter}/{extinction_limit}")
              print(f"           Current Best F1: {best_f1:.4f} (Gen {best_gen})")

          # --- MASS EXTINCTION EVENT ---
          if stagnation_counter >= extinction_limit:
               print(f"💀 [Flight]: MASS EXTINCTION. 100% of population sanitized. Rebooting evolution...")
               with torch.no_grad():
                    # Complete reset of the population DNA
                    new_population = torch.randint(
                         0, total_features, 
                         (config["POP_SIZE"], config["GENE_COUNT"]), 
                         device=device, 
                         dtype=reactor.population.dtype
                    )
                    reactor.population = new_population
                    # Reset internal gene metrics to allow new pioneers to emerge
                    reactor.gene_scores.fill_(0.0)
                    reactor.gene_usage.fill_(0.0)
               stagnation_counter = 0 

          # --- RADIATION STAGNATION BREAKER ---
          elif stagnation_counter > 0 and stagnation_counter % stagnation_limit == 0:
               print(f"☢️  [Flight]: CRITICAL STAGNATION. Injecting radiation into 40% of population...")
               with torch.no_grad():
                    n_nuke = int(config["POP_SIZE"] * 0.40)
                    indices = torch.randperm(config["POP_SIZE"], device=device)[:n_nuke]
                    
                    # Generate new random gene indices using total_features as the upper bound
                    new_dna = torch.randint(
                         0, total_features, 
                         (n_nuke, config["GENE_COUNT"]), 
                         device=device, 
                         dtype=reactor.population.dtype
                    )
                    reactor.population[indices] = new_dna
               # We don't reset stagnation_counter here, as we are still approaching the 60-gen extinction limit

          vitality = (reactor.gene_scores + 0.1) / (reactor.gene_usage + 1.0)
          top_v, top_i = torch.topk(vitality, k=10)
          
          print(f"\n🧬 [Gen {gen} Gene Vitality Top 10]:")
          for rank, (val, idx) in enumerate(zip(top_v, top_i)):
                name = reactor.feature_names[idx.item()]
                print(f"   1. {name:<20} | Score: {val.item():.4f}")

          if gen < generations:
               temperature = torch.cuda.temperature()
               if  temperature > hotness_max:
                    print(f"🔥 [Space]: Radiation spike ({temperature}°C). Orbiting to the dark side of the planet.")
                    while True:
                         time.sleep(1.0)
                         temperature = torch.cuda.temperature()
                         if temperature <= hotness_min:
                              print(f"🛰️ [Space]: Thermal equilibrium reached ({temperature}°C). Exiting eclipse. Main drive re-engaged.")
                              break
                    
               reactor.evolve(metrics)
     
     print("\n" + "—"*60)
     print(f"🏁 [Flight]: Flight Path Complete.")
     print(f"🥇 [Best Result]: Gen {best_gen} achieved F1 {best_f1:.4f}")
     print("—"*60)

     print("\n🛰️ [Flight]: Draining the Oort Cloud...")
     time.sleep(1)
     
     del reactor
     if torch.cuda.is_available():
          torch.cuda.empty_cache()
     
     print("✅ [Flight]: Test run complete. Singularity stable.")

if __name__ == "__main__":
    try:
        run_test_flight()
    except Exception as e:
        import traceback
        print(f"💥 [Flight Critical]: System failure: {e}")
        traceback.print_exc()
        sys.exit(1)