"""
===============================================================================
File:        space.py
Author:      JP Ueberbach
Created:     2026-02-23

Description:
    Core infrastructure module for the MilkyWay ML universe.

    This module defines the abstract and concrete orchestration layers
    required to run evolutionary model discovery within a configurable
    feature universe. It provides base abstractions for:

        - Universe definitions (feature spaces and preprocessing)
        - Flight engines (evolutionary optimization loops)
        - Singularities (trainable predictive cores)
        - Comets (asynchronous persistence backends)
        - Normalizers (feature scaling modules)
        - Lenses (loss functions)

    The architecture is fully config-driven and supports dynamic
    class loading, GPU acceleration, evolutionary stagnation handling,
    thermal protection, and asynchronous checkpointing.

Key Capabilities:
    - Config-resolved dynamic factory loading
    - Evolutionary flight loop with extinction and radiation logic
    - Asynchronous model and artifact persistence
    - GPU-aware execution and thermal monitoring
    - Abstract extensibility across all core components
===============================================================================
"""
from abc import ABC, abstractmethod
from typing import Any, Dict
from pathlib import Path
import os
import queue
import threading
import torch
import torch.nn as nn
import pandas as pd
import numpy as np
import time
import sys
import importlib
import random


class BaseFactory:
    """Base class for factories that resolve classes via config-style paths."""

    def _load_from_config_string(class_path: str):
        """
        Resolve and dynamically import a class from a dotted config path.

        Supports two loading strategies:
        1. Custom modules under the ``config.user`` directory.
        2. Standard Python import resolution for installed modules.

        Args:
            class_path (str):
                Fully-qualified dotted path to the class.

        Returns:
            Type:
                Resolved class reference.

        Raises:
            SystemExit:
                If the class cannot be resolved or imported.
        """
        parts = class_path.split('.')  # Split dotted path into module components
        class_name = parts.pop()  # Extract final token as class name
        
        # Handle custom config.user anchored modules
        if "config.user" in class_path:        
            path_str = class_path.replace(class_name, "").rstrip('.')  # Remove class name portion
            
            # Convert config.user dotted structure to filesystem path
            if path_str.startswith("config.user."):
                sub_path = path_str.replace("config.user.", "").replace(".", "/")
                file_path = Path(f"config.user/{sub_path}.py")
            else:
                file_path = Path(path_str.replace(".", "/") + ".py")
                
            if file_path.is_file():  # Ensure file exists before attempting dynamic load
                rand_id = random.randint(1000, 999999)  # Prevent module name collisions
                module_name = f"custom_module_{rand_id}"
                try:
                    spec = importlib.util.spec_from_file_location(module_name, file_path.resolve())
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    return getattr(module, class_name)  # Return resolved class
                except Exception as e:
                    print(f"Error loading {class_name} from {file_path}: {e}")
                    sys.exit(1)

        # Fallback to standard import mechanism
        try:
            module_path = ".".join(parts)
            module = importlib.import_module(module_path)
            return getattr(module, class_name)
        except Exception as e:
            print(f"Error: Could not resolve '{class_path}'.\n{e}")
            sys.exit(1)


class Universe(ABC):
    """Abstract base class for feature universes."""

    @abstractmethod
    def ignite(self):
        """
        Initialize and prepare the universe.

        Responsible for loading data, preparing features,
        and constructing internal state required for execution.
        """
        pass

    @abstractmethod
    def dimensions(self):
        """
        Return dimensional structure of the universe.

        Returns:
            Any:
                Metadata describing feature dimensionality.
        """
        pass

    @abstractmethod
    def features(self):
        """
        Return list of active feature names.

        Returns:
            list:
                Feature identifiers used by the universe.
        """
        pass

    @abstractmethod
    def bigbang(self):
        """
        Execute full normalization and preprocessing pipeline.

        Returns:
            Tuple[pd.DataFrame, pd.Series]:
                Processed features and aligned targets.
        """
        pass


class Normalizer(nn.Module, ABC):
    """
    Abstract base class for feature scaling modules.

    Normalizers define deterministic transformations that
    standardize or reshape feature distributions prior to training.
    """

    def __init__(self):
        super().__init__()

    @abstractmethod
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Apply normalization transform.

        Args:
            x (torch.Tensor):
                Input feature tensor.

        Returns:
            torch.Tensor:
                Normalized feature tensor.
        """
        pass


class Comet(ABC):
    """
    Abstract base class for asynchronous persistence backends.

    A Comet manages non-blocking artifact storage such as:
        - Model checkpoints
        - Logs
        - Gene dumps
    """

    def __init__(self, name: str, queue_size: int = 100):
        """
        Initialize comet and start orbital worker thread.

        Args:
            name (str):
                Name identifier for comet instance.
            queue_size (int):
                Maximum buffered artifacts before blocking.
        """
        self.name = name  # Comet identity
        self._trail = queue.Queue(maxsize=queue_size)  # Artifact queue
        self._nucleus = threading.Thread(target=self._orbital_loop, daemon=True)  # Worker thread
        
        os.makedirs('checkpoints', exist_ok=True)  # Ensure checkpoint directory exists
        os.makedirs('logs', exist_ok=True)  # Ensure log directory exists
        
        self._nucleus.start()  # Start background persistence worker
        print(f"☄️ [Space]: Establishing Orbit for {self.name}. Tail length: {queue_size}")

    def _orbital_loop(self):
        """
        Continuously consume artifacts from queue and eject them.

        Terminates when sentinel ``None`` is received.
        """
        while True:
            item = self._trail.get()
            if item is None:
                break  # Exit loop on shutdown signal
                
            filename, data, is_model = item
            try:
                self.eject(filename, data, is_model)  # Delegate persistence logic
            except Exception as e:
                print(f"❌ [Comet {self.name} Error]: Critical failure in ejection: {e}")
            finally:
                self._trail.task_done()

    @abstractmethod
    def eject(self, filename: str, data: Any, is_model: bool):
        """
        Persist artifact to storage backend.

        Args:
            filename (str):
                Target file name.
            data (Any):
                Object to persist.
            is_model (bool):
                Indicates if artifact represents model weights.
        """
        pass

    def deposit(self, filename: str, data: Any, is_model: bool = False, is_gene_dump: bool = False):
        """
        Queue artifact for asynchronous persistence.

        Args:
            filename (str):
                Output file name.
            data (Any):
                Artifact payload.
            is_model (bool):
                If True, block on full queue.
            is_gene_dump (bool):
                Reserved flag for gene persistence.
        """
        try:
            self._trail.put((filename, data, is_model), block=False)  # Non-blocking enqueue
        except queue.Full:
            if not is_model:
                pass  # Drop non-critical artifacts
            else:
                self._trail.put((filename, data, is_model), block=True)  # Block for critical models

    def dissipate(self):
        """
        Gracefully shut down comet worker thread.
        """
        self._trail.put(None)  # Send sentinel
        self._nucleus.join()  # Wait for thread termination
        print(f"☄️ [Comet {self.name}]: Dissipated into the cosmos.")


class BaseFlight(ABC):
    """
    Abstract base class for evolutionary orchestration engines.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize base flight state.

        Args:
            config (Dict[str, Any]):
                Configuration dictionary.
        """
        self.config = config  # Flight configuration
        self.best_f1 = -1.0  # Track best F1 score observed
        self.best_gen = 0  # Generation of best score
        self.stagnation_counter = 0  # Generations without improvement
        self.universe = None  # Attached universe
        self.singularity = None  # Attached singularity
        self.device = None  # Execution device

    @abstractmethod
    def warp(self, singularity):
        """
        Execute main evolutionary loop.

        Args:
            singularity:
                Predictive core instance.
        """
        pass

    @abstractmethod
    def cleanup(self):
        """
        Release memory and resources after flight completion.
        """
        pass


class Flight(BaseFlight):
    """
    Concrete evolutionary flight implementation.

    Implements stagnation detection, extinction resets,
    radiation diversification, and thermal monitoring.
    """

    def warp(self, singularity):
        """
        Run full evolutionary optimization loop.

        Args:
            singularity:
                Configured singularity instance.
        """
        self.singularity = singularity  # Attach predictive core
        singularity.wormhole(self)  # Bridge flight context
        self.universe = singularity.universe  # Access universe
        self.device = singularity.config.get('device', 'cpu')  # Execution device

        if not self.singularity or not self.universe:
            raise RuntimeError("Flight Engine failure: Singularity or Universe not initialized.")

        total_features = len(self.universe.features())  # Feature space size
        
        settings = self.config.get('settings', {})  # Extract nested settings
        generations = self.config.get('max_generations', 4000)
        extinction_limit = settings.get('extinction_stagnation', 60)
        stagnation_limit = settings.get('radiation_stagnation', 20)
        hotness_max = settings.get('hotness_max', 87)
        hotness_min = settings.get('hotness_min', 80)
        population_size = settings.get('population_size', 1000)
        gene_count = settings.get('gene_count', 16)

        for gen in range(1, generations + 1):  # Iterate evolutionary generations
            print(f"\n" + "="*60)
            print(f"🚀 [Flight]: Commencing Generation {gen}/{generations}")
            print("="*60)

            start_t = time.time()  # Start generation timer
            metrics = self.singularity.run_generation(self.universe)  # Evaluate population
            duration = time.time() - start_t  # Compute runtime

            fitness = metrics["score"]  # Extract fitness scores
            avg_f1 = metrics["f1"].mean().item()
            max_f1 = metrics["f1"].max().item()
            avg_prec = metrics["precision"].mean().item()
            max_prec = metrics["precision"].max().item()
            total_sigs = metrics["sigs"].sum().item()

            print(f"\n📊 [Gen {gen} Summary] ({duration:.1f}s)")
            print(f"   F1:         Avg {avg_f1:.4f} | Max {max_f1:.4f}")
            print(f"   Precision: Avg {avg_prec:.4f} | Max {max_prec:.4f}")
            print(f"   Activity:  Total Sigs {int(total_sigs)} | Density {metrics['density'].mean().item():.4%}")

            if max_f1 > self.best_f1:  # Check for improvement
                print(f"🏆 [Flight]: New High Water Mark! {max_f1:.4f} beats {self.best_f1:.4f}")
                self.best_f1 = max_f1
                self.best_gen = gen
                self.stagnation_counter = 0

                winner_idx = torch.argmax(fitness).item()  # Identify best genome
                filename = f"model-best-gen{gen}-f1-{max_f1:.4f}.pt"
                self.singularity.save_state(self.universe, filename, winner_idx=winner_idx)
            else:
                self.stagnation_counter += 1  # Increment stagnation
                print(f"📉 [Flight]: No improvement. Stagnation: {self.stagnation_counter}/{extinction_limit}")
                print(f"           Current Best F1: {self.best_f1:.4f} (Gen {self.best_gen})")

            if self.stagnation_counter >= extinction_limit:  # Mass extinction reset
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

            self._print_vitality()  # Display gene vitality metrics

            if gen < generations:
                self._manage_thermals(hotness_max, hotness_min)  # Protect GPU
                self.singularity.evolve(metrics)  # Advance population

        print("\n" + "—"*60)
        print(f"🏁 [Flight]: Flight Path Complete.")
        print(f"🥇 [Best Result]: Gen {self.best_gen} achieved F1 {self.best_f1:.4f}")
        print("—"*60)

    def _print_vitality(self):
        """
        Display top genes ranked by vitality ratio.

        Vitality is computed as adjusted score divided by usage frequency.
        """
        vitality = (self.singularity.gene_scores + 0.1) / (self.singularity.gene_usage + 1.0)
        top_v, top_i = torch.topk(vitality, k=10)
        print(f"\n🧬 [Gene Vitality Top 10]:")
        for rank, (val, idx) in enumerate(zip(top_v, top_i)):
            name = self.singularity.feature_names[idx.item()]
            print(f"   {rank+1}. {name:<20} | Score: {val.item():.4f}")

    def _manage_thermals(self, max_temp: float, min_temp: float):
        """
        Monitor GPU temperature and pause execution if overheated.

        Args:
            max_temp (float):
                Upper safe temperature threshold.
            min_temp (float):
                Resume threshold after cooldown.
        """
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
        Release GPU memory and destroy singularity reference.
        """
        print("\n🛰️ [Flight]: Draining the Oort Cloud...")
        time.sleep(1)
        
        if self.singularity:
            del self.singularity  # Remove singularity reference
        
        if torch.cuda.is_available():
            torch.cuda.empty_cache()  # Free GPU cache
            
        print("✅ [Flight]: Cleanup complete. Singularity stable.")


class Singularity(ABC):
    """
    Abstract predictive core.

    Responsible for training, inference,
    tensor conversion, and weight persistence.
    """

    def __init__(self, device: str = "cuda" if torch.cuda.is_available() else "cpu"):
        """
        Initialize singularity on specified device.

        Args:
            device (str):
                Execution device identifier.
        """
        self.device = torch.device(device)  # Resolve device
        self.model = None  # Placeholder for torch model
        print(f"🌀 [Singularity]: Initialized on {self.device}")

    @abstractmethod
    def compress(self, features: pd.DataFrame, targets: pd.Series):
        """
        Train singularity model.

        Args:
            features (pd.DataFrame):
                Input feature matrix.
            targets (pd.Series):
                Target labels.
        """
        pass

    @abstractmethod
    def emit(self, features: pd.DataFrame) -> np.ndarray:
        """
        Perform inference on new feature data.

        Args:
            features (pd.DataFrame):
                Feature matrix.

        Returns:
            np.ndarray:
                Prediction outputs.
        """
        pass

    def to_tensor(self, df: pd.DataFrame) -> torch.Tensor:
        """
        Convert pandas DataFrame to device tensor.

        Args:
            df (pd.DataFrame):
                Input dataframe.

        Returns:
            torch.Tensor:
                Tensor on configured device.
        """
        return torch.tensor(df.values, dtype=torch.float32).to(self.device)

    @abstractmethod
    def save_state(self, path: str):
        """
        Persist model weights to disk.

        Args:
            path (str):
                Output file path.
        """
        pass


class Lens(nn.Module, ABC):
    """
    Abstract base class for loss functions.

    Defines how prediction errors are computed.
    """

    def __init__(self):
        super().__init__()

    @abstractmethod
    def forward(self, inputs: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        """
        Compute loss between predictions and targets.

        Args:
            inputs (torch.Tensor):
                Model outputs.
            targets (torch.Tensor):
                Ground truth values.

        Returns:
            torch.Tensor:
                Scalar loss tensor.
        """
        pass