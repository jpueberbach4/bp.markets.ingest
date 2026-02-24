import time
import torch
from datetime import datetime
from typing import Dict, Any
from ml.space.space import Singularity, Flight

class MilleniumFalcon(Flight):
    """
    Orchestrates the evolutionary training loop for a Singularity.
    Handles thermal management, mass extinction events, and model checkpoints.
    Includes diagnostic tracking to print exact signal firing locations.
    """
    def __init__(self, config):
        # State Tracking
        self.config = config
        self.best_f1 = -1.0
        self.best_gen = 0
        self.stagnation_counter = 0
        self.universe = None

    def warp(self, singularity: Singularity):
        """
        Runs the main evolutionary loop with an extended stagnation runway.
        """
        self.singularity = singularity
        self.universe = singularity.universe

        if not self.singularity or not self.universe:
            raise RuntimeError("Engine not prepared. Call prepare_engine() first.")

        print(f"🚀 [Flight]: Firing up warp-drive of MILLENIUMFALCON")

        total_features = len(self.universe.features())
        generations = self.config.get('max_generations', 4000)
        settings = self.config.get('settings')
        
        # --- TUNED EVOLUTIONARY PARAMETERS ---
        # Increased limit to give models time to optimize selectivity/precision
        extinction_limit = settings.get('extinction_stagnation', 120) 
        radiation_stagnation = settings.get('radiation_stagnation', 20)
        min_sigs_required = settings.get('min_signals', 10)
        
        hotness_max = settings.get('hotness_max', 87)
        hotness_min = settings.get('hotness_min', 80)
        population_size = settings.get('population_size', 1000)
        gene_count = settings.get('gene_count', 16)

        self.device = singularity.config.get('device')

        for gen in range(1, generations + 1):
            print(f"\n" + "="*60)
            print(f"🚀 [Flight]: Commencing Generation {gen}/{generations}")
            print("="*60)

            start_t = time.time()
            metrics = self.singularity.run_generation(self.universe)
            duration = time.time() - start_t

            # Extract Metrics
            fitness = metrics["score"]
            avg_f1 = metrics["f1"].mean().item()
            max_f1 = metrics["f1"].max().item()
            avg_prec = metrics["precision"].mean().item()
            max_prec = metrics["precision"].max().item()
            total_sigs = metrics["sigs"].sum().item()
            
            # Extract specific winner signals to prevent "Ghost" saving
            winner_idx = torch.argmax(metrics["f1"]).item()
            winner_sigs = metrics["sigs"][winner_idx].sum().item()

            print(f"\n📊 [Gen {gen} Summary] ({duration:.1f}s)")
            print(f"   F1:         Avg {avg_f1:.4f} | Max {max_f1:.4f}")
            print(f"   Precision: Avg {avg_prec:.4f} | Max {max_prec:.4f}")
            print(f"   Activity:  Total Sigs {int(total_sigs)} | Density {metrics['density'].mean().item():.4%}")
            print(f"   Winner Sigs: {int(winner_sigs)}")

            # --- DIAGNOSTIC: Print where the winner actually fired ---
            self._diagnose_signals(metrics, winner_idx)

            # [2026-02-21] REQUIREMENT: Only save models with HIGHER F1 than previous
            # AND must meet the minimum signal ground truth to avoid 'ghost' models.
            if max_f1 > self.best_f1:
                if winner_sigs >= min_sigs_required:
                    print(f"🏆 [Flight]: New Alpha Peak! {max_f1:.4f} beats {self.best_f1:.4f}")
                    self.best_f1 = max_f1
                    self.best_gen = gen
                    self.stagnation_counter = 0

                    # Find winner and save
                    filename = f"model-best-gen{gen}-f1-{max_f1:.4f}.pt"
                    self.singularity.save_state(self.universe, filename, winner_idx=winner_idx)
                else:
                    self.stagnation_counter += 1
                    print(f"⚠️ [Flight]: F1 {max_f1:.4f} rejected. Winner signals ({int(winner_sigs)}) below minimum ({min_sigs_required}).")
                    print(f"📉 [Flight]: Stagnation: {self.stagnation_counter}/{extinction_limit}")
            else:
                self.stagnation_counter += 1
                print(f"📉 [Flight]: No improvement. Stagnation: {self.stagnation_counter}/{extinction_limit}")
                print(f"           Current Best F1: {self.best_f1:.4f} (Gen {self.best_gen})")

            # --- MASS EXTINCTION EVENT ---
            if self.stagnation_counter >= extinction_limit:
                print(f"💀 [Flight]: MASS EXTINCTION. Stagnation limit {extinction_limit} reached. Resetting...")
                with torch.no_grad():
                    new_population = torch.randint(
                        0, total_features,
                        (population_size, gene_count),
                        device=self.device,
                        dtype=self.singularity.population.dtype
                    )
                    self.singularity.population = new_population
                    self.singularity.gene_scores.fill_(0.0)
                    self.singularity.gene_usage.fill_(0.0)
                self.stagnation_counter = 0

            # --- RADIATION STAGNATION BREAKER (MUTATION FLARE) ---
            # Triggers every radiation_stagnation generations to shake up local minima
            elif self.stagnation_counter > 0 and self.stagnation_counter % radiation_stagnation == 0:
                mutation_rate = 0.40
                # If we are deep into stagnation (>50%), intensify the radiation
                if self.stagnation_counter > (extinction_limit // 2):
                    print(f"☢️  [Flight]: DEEP STAGNATION. Intensifying radiation (60% mutation)...")
                    mutation_rate = 0.60
                else:
                    print(f"☢️  [Flight]: Injecting radiation into 40% of population...")
                
                with torch.no_grad():
                    n_nuke = int(population_size * mutation_rate)
                    indices = torch.randperm(population_size, device=self.device)[:n_nuke]
                    new_dna = torch.randint(
                        0, total_features,
                        (n_nuke, gene_count),
                        device=self.device,
                        dtype=self.singularity.population.dtype
                    )
                    self.singularity.population[indices] = new_dna

            # Display Gene Vitality
            self._print_vitality()

            # --- THERMAL MANAGEMENT ---
            if gen < generations:
                self._manage_thermals(hotness_max, hotness_min)
                self.singularity.evolve(metrics)

        print("\n" + "—"*60)
        print(f"🏁 [Flight]: Flight Path Complete.")
        print(f"🥇 [Best Result]: Gen {self.best_gen} achieved F1 {self.best_f1:.4f}")
        print("—"*60)

    def _diagnose_signals(self, metrics: Dict[str, Any], model_idx: int):
        """
        Extracts and prints the exact array indices (bars) where the model fired.
        Useful for cross-referencing against your original Pandas DataFrame.
        """
        raw_tensor = None
        
        # Check standard possible keys for the un-aggregated time-series signal tensor
        if "signal_map" in metrics:
            raw_tensor = metrics["signal_map"][model_idx]
        elif "sigs" in metrics and metrics["sigs"].dim() > 1:
            raw_tensor = metrics["sigs"][model_idx]
            
        if raw_tensor is not None:
            sig_locations = torch.where(raw_tensor > 0)[0]
            if len(sig_locations) > 0:
                locs = sig_locations.tolist()
                # Print up to the first 20 locations so it doesn't flood the terminal
                print(f"   🔍 [Diagnostic]: Model {model_idx} fired at bars: {locs[:20]}{'...' if len(locs)>20 else ''}")
            else:
                print(f"   🔍 [Diagnostic]: Model {model_idx} fired 0 actual bits in the time-series tensor.")
        else:
            print(f"   🔍 [Diagnostic]: Time-series tensor unavailable in metrics. Check Singularity output.")

    def _print_vitality(self):
        """Displays the top 10 genes based on vitality score."""
        vitality = (self.singularity.gene_scores + 0.1) / (self.singularity.gene_usage + 1.0)
        top_v, top_i = torch.topk(vitality, k=10)
        print(f"\n🧬 [Gene Vitality Top 10]:")
        for rank, (val, idx) in enumerate(zip(top_v, top_i)):
            name = self.singularity.feature_names[idx.item()]
            print(f"   {rank+1}. {name:<20} | Score: {val.item():.4f}")

    def _manage_thermals(self, max_temp: float, min_temp: float):
        """Monitors GPU temperature to prevent hardware throttle or damage."""
        if self.device == "cuda":
            try:
                temperature = torch.cuda.temperature() # Custom or platform specific
            except AttributeError:
                return # Skip if hardware polling isn't available

            if temperature > max_temp:
                print(f"🔥 [Space]: Radiation spike ({temperature}°C). Orbiting to dark side...")
                while temperature > min_temp:
                    # Increased to 5 seconds to prevent thermal loops
                    time.sleep(5.0) 
                    temperature = torch.cuda.temperature()
                print(f"🛰️ [Space]: Thermal equilibrium reached ({temperature}°C). Main drive re-engaged.")

    def cleanup(self):
        """Clears memory and drains the system cache."""
        print("\n🛰️ [Flight]: Draining the Oort Cloud...")
        if hasattr(self, 'singularity'):
            del self.singularity
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        print("✅ [Flight]: Cleanup complete. Singularity stable.")