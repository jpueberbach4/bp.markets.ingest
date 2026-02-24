"""
===============================================================================
File:        milkyway.py
Author:      JP Ueberbach
Created:     2026-02-23

Description:
    Implementation of the MilkyWay Universe within the ML space.

    MilkyWay manages:
        - Data ingestion and temporal boundaries
        - Initialization of Comets and Normalizers
        - Feature and target preprocessing
        - BigBang normalization applying multiple Normalizers
        - Auditing of string-polluted and NaN dimensions
        - Ejection of payloads to comets (models, gene dumps, logs)

Key Capabilities:
    - Config-driven universe instantiation
    - Cosmic normalization pipeline (Redshift, Kinematics)
    - Statistical auditing and reporting
    - Integration with Comet and Normalizer factories
===============================================================================
"""
from abc import ABC, abstractmethod
from typing import Any, Dict
import os
import queue
import threading
import torch
import torch.nn as nn
import pandas as pd
import numpy as np
import time

# Mocking the data provider - ensure this is available in your environment
# from your_data_module import get_data 

class Universe(ABC):
    """Baseclass for feature universes."""
    @abstractmethod
    def ignite(self): pass

    @abstractmethod
    def dimensions(self): pass

    @abstractmethod
    def features(self): pass

    @abstractmethod
    def bigbang(self): pass

class Normalizer(nn.Module, ABC):
    """
    Abstract Base Class for feature scaling.
    Defines the laws of atmospheric entry for raw data.
    """
    def __init__(self):
        super().__init__()

    @abstractmethod
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        pass

class Comet(ABC):
    """
    Abstract Base Class for the Async Data Comet.
    Defines the orbital mechanics for non-blocking data ejection.
    """

    def __init__(self, name: str, queue_size: int = 100):
        self.name = name
        self._trail = queue.Queue(maxsize=queue_size)
        self._nucleus = threading.Thread(target=self._orbital_loop, daemon=True)
        
        # Standardize the planetary storage environment
        os.makedirs('checkpoints', exist_ok=True)
        os.makedirs('logs', exist_ok=True)
        
        self._nucleus.start()
        print(f"☄️ [Space]: Establishing Orbit for {self.name}. Tail length: {queue_size}")

    def _orbital_loop(self):
        """Standardizes the loop that consumes the trail."""
        while True:
            item = self._trail.get()
            if item is None: 
                break
                
            filename, data, is_model = item
            try:
                self.eject(filename, data, is_model)
            except Exception as e:
                print(f"❌ [Comet {self.name} Error]: Critical failure in ejection: {e}")
            finally:
                self._trail.task_done()

    @abstractmethod
    def eject(self, filename: str, data: Any, is_model: bool):
        """
        The concrete implementation of how matter is written to the void.
        Must be implemented by specific comet types.
        """
        pass

    def deposit(self, filename: str, data: Any, is_model: bool = False, is_gene_dump: bool = False):
        """
        Public method to add matter to the trail without blocking the main thread.
        """
        try:
            self._trail.put((filename, data, is_model), block=False)
        except queue.Full:
            if not is_model:
                # Discard logs to preserve velocity
                pass 
            else:
                # Block for models; we cannot lose the mass of a new discovery
                self._trail.put((filename, data, is_model), block=True)

    def dissipate(self):
        """Gracefully ends the comet's flight path."""
        self._trail.put(None)
        self._nucleus.join()
        print(f"☄️ [Comet {self.name}]: Dissipated into the cosmos.")


class BaseFlight(ABC):
    """
    Abstract Base Class for Singularity Orchestration.
    Defines the structural requirements for any evolutionary flight path.
    """
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.best_f1 = -1.0
        self.best_gen = 0
        self.stagnation_counter = 0
        self.universe = None
        self.singularity = None
        self.device = None

    @abstractmethod
    def warp(self, singularity):
        """
        Must implement the entry point for the evolutionary loop.
        """
        pass

    @abstractmethod
    def cleanup(self):
        """
        Must implement memory drainage and system stabilization.
        """
        pass

class Flight(BaseFlight):
    """
    Standard implementation of a Singularity Flight.
    Handles thermal management, mass extinction events, and model checkpoints.
    """
    def warp(self, singularity):
        """
        Runs the main evolutionary loop by injecting the Singularity into its Universe.
        """
        self.singularity = singularity
        
        # Bridge the Singularity to the Flight environment
        singularity.wormhole(self)
        self.universe = singularity.universe
        
        # Extract device from singularity physics
        self.device = singularity.config.get('device', 'cpu')

        if not self.singularity or not self.universe:
            raise RuntimeError("Flight Engine failure: Singularity or Universe not initialized.")

        # Universe Physics
        total_features = len(self.universe.features())
        
        # Configuration Extraction
        settings = self.config.get('settings', {})
        generations = self.config.get('max_generations', 4000)
        extinction_limit = settings.get('extinction_stagnation', 60)
        stagnation_limit = settings.get('radiation_stagnation', 20)
        hotness_max = settings.get('hotness_max', 87)
        hotness_min = settings.get('hotness_min', 80)
        population_size = settings.get('population_size', 1000)
        gene_count = settings.get('gene_count', 16)

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

            print(f"\n📊 [Gen {gen} Summary] ({duration:.1f}s)")
            print(f"   F1:         Avg {avg_f1:.4f} | Max {max_f1:.4f}")
            print(f"   Precision: Avg {avg_prec:.4f} | Max {max_prec:.4f}")
            print(f"   Activity:  Total Sigs {int(total_sigs)} | Density {metrics['density'].mean().item():.4%}")

            # Improvement Check (Persistence logic: only save if F1 improves)
            if max_f1 > self.best_f1:
                print(f"🏆 [Flight]: New High Water Mark! {max_f1:.4f} beats {self.best_f1:.4f}")
                self.best_f1 = max_f1
                self.best_gen = gen
                self.stagnation_counter = 0

                # Find winner and save state
                winner_idx = torch.argmax(fitness).item()
                filename = f"model-best-gen{gen}-f1-{max_f1:.4f}.pt"
                self.singularity.save_state(self.universe, filename, winner_idx=winner_idx)
            else:
                self.stagnation_counter += 1
                print(f"📉 [Flight]: No improvement. Stagnation: {self.stagnation_counter}/{extinction_limit}")
                print(f"           Current Best F1: {self.best_f1:.4f} (Gen {self.best_gen})")

            # --- MASS EXTINCTION EVENT ---
            if self.stagnation_counter >= extinction_limit:
                print(f"💀 [Flight]: MASS EXTINCTION. Rebooting evolution...")
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

            # --- RADIATION STAGNATION BREAKER ---
            elif self.stagnation_counter > 0 and self.stagnation_counter % stagnation_limit == 0:
                print(f"☢️  [Flight]: CRITICAL STAGNATION. Injecting radiation into 40% of population...")
                with torch.no_grad():
                    n_nuke = int(population_size * 0.40)
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
            temperature = torch.cuda.temperature()
            if temperature > max_temp:
                print(f"🔥 [Space]: Radiation spike ({temperature}°C). Orbiting to dark side...")
                while temperature > min_temp:
                    time.sleep(1.0)
                    temperature = torch.cuda.temperature()
                print(f"🛰️ [Space]: Thermal equilibrium reached ({temperature}°C). Main drive re-engaged.")

    def cleanup(self):
        """
        Clears memory and drains the system cache.
        """
        print("\n🛰️ [Flight]: Draining the Oort Cloud...")
        time.sleep(1)
        
        if self.singularity:
            del self.singularity
        
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            
        print("✅ [Flight]: Cleanup complete. Singularity stable.")



class Singularity(ABC):
    """
    The computational core where the multi-dimensional feature space
    collapses into a predictive output.
    """

    def __init__(self, device: str = "cuda" if torch.cuda.is_available() else "cpu"):
        self.device = torch.device(device)
        self.model = None
        print(f"🌀 [Singularity]: Initialized on {self.device}")

    @abstractmethod
    def compress(self, features: pd.DataFrame, targets: pd.Series):
        """
        The entry point for the Big Bang matter. 
        Should handle tensor conversion and the start of the 'collapse' (training).
        """
        pass

    @abstractmethod
    def emit(self, features: pd.DataFrame) -> np.ndarray:
        """
        The inference path. Takes a coordinate space and 
        emits a prediction signal.
        """
        pass

    def to_tensor(self, df: pd.DataFrame) -> torch.Tensor:
        """
        Standardizes the transition of matter from CPU/Pandas 
        to GPU/Torch.
        """
        return torch.tensor(df.values, dtype=torch.float32).to(self.device)

    @abstractmethod
    def save_state(self, path: str):
        """Preserves the singularity's current mass (weights)."""
        pass

class Lens(nn.Module, ABC):
    """
    Abstract Base Class for all loss functions.
    A Lens defines how the Singularity perceives its own errors.
    """
    def __init__(self):
        super().__init__()

    @abstractmethod
    def forward(self, inputs: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        """
        Calculates the divergence between the Singularity's 
        output and the ground truth.
        """
        pass

