"""
===============================================================================
File:        milleniumfalcon.py
Author:      JP Ueberbach
Created:     2026-02-23

Description:
    Implementation of the MilleniumFalcon flight orchestrator within the ML space.

    MilleniumFalcon handles the evolutionary training loop of a Singularity,
    including:
        - Thermal management for GPU safety
        - Mass extinction and mutation events to avoid stagnation
        - Checkpointing models based on F1 performance
        - Diagnostic tracking of signal locations
        - Vitality scoring of genes

Key Capabilities:
    - Evolutionary orchestration of singularities
    - Population stagnation handling and mutation flares
    - Detailed F1/precision logging
    - Safe checkpoint and cache management
===============================================================================
"""

import time
from typing import Dict, Any

import torch
from ml.space.space import Singularity, Flight


class MilleniumFalcon(Flight):
    """Orchestrates the evolutionary training loop for a Singularity."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize flight with configuration and tracking state.

        Args:
            config (Dict[str, Any]): Configuration dictionary for evolutionary parameters.
        """
        self.config = config
        self.best_f1: float = -1.0
        self.best_gen: int = 0
        self.stagnation_counter: int = 0
        self.universe = None

    def warp(self, singularity: Singularity):
        """Run the main evolutionary training loop with stagnation and thermal management.

        Args:
            singularity (Singularity): Singularity object to train and evolve.
        """
        self.singularity = singularity
        self.universe = singularity.universe

        if not self.singularity or not self.universe:
            raise RuntimeError("Engine not prepared. Ensure Singularity and Universe are initialized.")

        print(f"🚀 [Flight]: Firing up warp-drive of MilleniumFalcon")

        total_features = len(self.universe.features())
        generations = self.config.get("max_generations", 4000)
        settings = self.config.get("settings", {})

        # Evolutionary parameters
        extinction_limit = settings.get("extinction_stagnation", 120)
        radiation_stagnation = settings.get("radiation_stagnation", 20)
        min_sigs_required = settings.get("min_signals", 10)
        hotness_max = settings.get("hotness_max", 87)
        hotness_min = settings.get("hotness_min", 80)
        population_size = settings.get("population_size", 1000)
        gene_count = settings.get("gene_count", 16)

        self.device = singularity.config.get("device")

        for gen in range(1, generations + 1):
            print("\n" + "=" * 60)
            print(f"🚀 [Flight]: Commencing Generation {gen}/{generations}")
            print("=" * 60)

            start_t = time.time()
            metrics = self.singularity.run_generation(self.universe)
            duration = time.time() - start_t

            # Extract key metrics
            fitness = metrics["score"]
            avg_f1 = metrics["f1"].mean().item()
            max_f1 = metrics["f1"].max().item()
            avg_prec = metrics["precision"].mean().item()
            max_prec = metrics["precision"].max().item()
            total_sigs = metrics["sigs"].sum().item()
            winner_idx = torch.argmax(metrics["f1"]).item()
            winner_sigs = metrics["sigs"][winner_idx].sum().item()

            print(f"\n📊 [Gen {gen} Summary] ({duration:.1f}s)")
            print(f"   F1:         Avg {avg_f1:.4f} | Max {max_f1:.4f}")
            print(f"   Precision:  Avg {avg_prec:.4f} | Max {max_prec:.4f}")
            print(f"   Activity:   Total Sigs {int(total_sigs)} | Density {metrics['density'].mean().item():.4%}")
            print(f"   Winner Sigs: {int(winner_sigs)}")

            self._diagnose_signals(metrics, winner_idx)

            # Save models with improved F1 and sufficient signals
            if max_f1 > self.best_f1 and winner_sigs >= min_sigs_required:
                print(f"🏆 [Flight]: New Alpha Peak! {max_f1:.4f} beats {self.best_f1:.4f}")
                self.best_f1 = max_f1
                self.best_gen = gen
                self.stagnation_counter = 0

                filename = f"model-best-gen{gen}-f1-{max_f1:.4f}.pt"
                self.singularity.save_state(self.universe, filename, winner_idx=winner_idx)

            else:
                self.stagnation_counter += 1
                if max_f1 <= self.best_f1:
                    print(f"📉 [Flight]: No improvement. Stagnation: {self.stagnation_counter}/{extinction_limit}")
                    print(f"           Current Best F1: {self.best_f1:.4f} (Gen {self.best_gen})")
                else:
                    print(f"⚠️ [Flight]: F1 {max_f1:.4f} rejected. Winner signals ({int(winner_sigs)}) below minimum ({min_sigs_required})")
                    print(f"📉 [Flight]: Stagnation: {self.stagnation_counter}/{extinction_limit}")

            # Mass extinction: reset population if stagnation limit reached
            if self.stagnation_counter >= extinction_limit:
                print(f"💀 [Flight]: MASS EXTINCTION. Stagnation limit reached. Resetting...")
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

            # Radiation stagnation breaker (mutation flare)
            elif self.stagnation_counter > 0 and self.stagnation_counter % radiation_stagnation == 0:
                mutation_rate = 0.40
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

            self._print_vitality()
            if gen < generations:
                self._manage_thermals(hotness_max, hotness_min)
                self.singularity.evolve(metrics)

        print("\n" + "—" * 60)
        print(f"🏁 [Flight]: Flight Path Complete.")
        print(f"🥇 [Best Result]: Gen {self.best_gen} achieved F1 {self.best_f1:.4f}")
        print("—" * 60)

    def _diagnose_signals(self, metrics: Dict[str, Any], model_idx: int):
        """Print exact indices where the model fired signals."""
        raw_tensor = None
        if "signal_map" in metrics:
            raw_tensor = metrics["signal_map"][model_idx]
        elif "sigs" in metrics and metrics["sigs"].dim() > 1:
            raw_tensor = metrics["sigs"][model_idx]

        if raw_tensor is not None:
            sig_locations = torch.where(raw_tensor > 0)[0].tolist()
            print(f"🔍 [Diagnostic]: Model {model_idx} fired at bars: {sig_locations[:20]}{'...' if len(sig_locations)>20 else ''}" 
                  if sig_locations else f"   🔍 [Diagnostic]: Model {model_idx} fired 0 signals.")
        else:
            print(f"🔍 [Diagnostic]: Time-series tensor unavailable. Check Singularity output.")

    def _print_vitality(self):
        """Displays top 10 genes based on vitality scores."""
        vitality = (self.singularity.gene_scores + 0.1) / (self.singularity.gene_usage + 1.0)
        top_v, top_i = torch.topk(vitality, k=10)
        print(f"\n🧬 [Gene Vitality Top 10]:")
        for rank, (val, idx) in enumerate(zip(top_v, top_i)):
            name = self.singularity.feature_names[idx.item()]
            print(f"   {rank+1}. {name:<20} | Score: {val.item():.4f}")

    def _manage_thermals(self, max_temp: float, min_temp: float):
        """Monitor GPU temperature to avoid hardware throttle or damage."""
        if self.device != "cuda":
            return
        try:
            temperature = torch.cuda.temperature()  # Custom or platform-specific
        except AttributeError:
            return

        if temperature > max_temp:
            print(f"🔥 [Space]: Radiation spike ({temperature}°C). Orbiting to dark side...")
            while temperature > min_temp:
                time.sleep(5.0)
                temperature = torch.cuda.temperature()
            print(f"🛰️ [Space]: Thermal equilibrium reached ({temperature}°C). Main drive re-engaged.")

    def cleanup(self):
        """Clear memory and empty CUDA cache."""
        print("\n🛰️ [Flight]: Draining the Oort Cloud...")
        if hasattr(self, "singularity"):
            del self.singularity
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        print("✅ [Flight]: Cleanup complete. Singularity stable.")