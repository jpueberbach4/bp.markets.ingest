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

        self.print("FLIGHT_WARP_INIT")

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
            self.print("FLIGHT_GEN_START", gen=gen, total=generations)
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

            self.print("FLIGHT_GEN_SUMMARY", gen=gen, duration=duration)
            self.print("FLIGHT_METRIC_F1", avg_f1=avg_f1, max_f1=max_f1)
            self.print("FLIGHT_METRIC_PREC", avg_prec=avg_prec, max_prec=max_prec)
            self.print("FLIGHT_METRIC_ACT", sigs=int(total_sigs), density=metrics['density'].mean().item())
            self.print("FLIGHT_METRIC_WINNER", sigs=int(winner_sigs))

            self._diagnose_signals(metrics, winner_idx)

            # Save models with improved F1 and sufficient signals
            if max_f1 > self.best_f1 and winner_sigs >= min_sigs_required:
                self.print("FLIGHT_ALPHA_PEAK", f1=max_f1, old_f1=self.best_f1)
                self.best_f1 = max_f1
                self.best_gen = gen
                self.stagnation_counter = 0

                filename = f"model-best-gen{gen}-f1-{max_f1:.4f}.pt"
                self.singularity.save_state(self.universe, filename, winner_idx=winner_idx)

            else:
                self.stagnation_counter += 1
                if max_f1 <= self.best_f1:
                    self.print("FLIGHT_STAGNATION", count=self.stagnation_counter, limit=extinction_limit)
                    self.print("FLIGHT_BEST_RECORD", f1=self.best_f1, gen=self.best_gen)
                else:
                    self.print("FLIGHT_REJECTED", f1=max_f1, sigs=int(winner_sigs), min=min_sigs_required)
                    self.print("FLIGHT_STAG_COUNT", count=self.stagnation_counter, limit=extinction_limit)

            # Mass extinction: reset population if stagnation limit reached
            if self.stagnation_counter >= extinction_limit:
                self.print("FLIGHT_EXTINCTION")
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
                    self.print("FLIGHT_RAD_DEEP")
                    mutation_rate = 0.60
                else:
                    self.print("FLIGHT_RAD_INJECT")
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
        self.print("FLIGHT_COMPLETE")
        self.print("FLIGHT_BEST_RESULT", gen=self.best_gen, f1=self.best_f1)
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
            if sig_locations:
                self.print("DIAG_SIGNALS", idx=model_idx, locs=sig_locations[:20], 
                           suffix='...' if len(sig_locations)>20 else '')
            else:
                self.print("DIAG_EMPTY", idx=model_idx)
        else:
            self.print("DIAG_UNAVAILABLE")

    def _print_vitality(self):
        """Displays top 10 genes based on vitality scores."""
        vitality = (self.singularity.gene_scores + 0.1) / (self.singularity.gene_usage + 1.0)
        top_v, top_i = torch.topk(vitality, k=10)
        self.print("GENE_VITALITY_HEADER")
        for rank, (val, idx) in enumerate(zip(top_v, top_i)):
            name = self.singularity.feature_names[idx.item()]
            self.print("GENE_VITALITY_ROW", rank=rank+1, name=name, score=val.item())

    def _manage_thermals(self, max_temp: float, min_temp: float):
        """Monitor GPU temperature with environment-safe fallback."""
        if self.device != "cuda":
            return
            
        def safe_get_temp():
            try:
                # Primary: Attempt the built-in PyTorch call
                return torch.cuda.temperature()
            except (AttributeError, TypeError):
                # Fallback: Direct NVML query (bypasses the PyTorch 2.6 string bug)
                try:
                    import pynvml
                    pynvml.nvmlInit()
                    handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                    temp = pynvml.nvmlDeviceGetTemperature(handle, 0)
                    pynvml.nvmlShutdown()
                    return temp
                except:
                    return None

        temperature = safe_get_temp()
        if temperature is None:
            return

        if temperature > max_temp:
            self.print("THERMAL_SPIKE", temp=temperature)
            while temperature is not None and temperature > min_temp:
                time.sleep(5.0)
                temperature = safe_get_temp()
            self.print("THERMAL_RESUME", temp=temperature)
            
    def cleanup(self):
        """Clear memory and empty CUDA cache."""
        self.print("CLEANUP_START")
        if hasattr(self, "singularity"):
            del self.singularity
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        self.print("CLEANUP_END")