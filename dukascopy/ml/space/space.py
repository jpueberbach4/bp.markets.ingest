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
from typing import Any, Dict, Tuple
from pathlib import Path
from datetime import datetime
import os
import queue
import threading
import torch
import torch.nn as nn
import pandas as pd
import time

from ml.space.base import BaseComet, BaseLens, BaseUniverse, BaseSingularity, BaseFlight, BaseNormalizer

# -----------------------------------------------------------------------------------------------------------

class Comet(BaseComet):
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
        self.print("COMET_ORBIT", name=self.name, size=queue_size)

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
                self.print("COMET_EJECTION_ERROR", name=self.name, e=e)
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
        self.print("COMET_DISSIPATE", name=self.name)

# -----------------------------------------------------------------------------------------------------------

class Flight(BaseFlight):
    """
    Concrete evolutionary flight implementation.

    Implements stagnation detection, extinction resets,
    radiation diversification, and thermal monitoring.
    """

    def warp(self, singularity):
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
                self.print("THERMAL_SPIKE", temperature=temperature)
                while temperature > min_temp:
                    time.sleep(1.0)
                    temperature = torch.cuda.temperature()
                self.print("THERMAL_RESUME", temperature=temperature)

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

# -----------------------------------------------------------------------------------------------------------

class Lens(nn.Module, BaseLens):
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

# -----------------------------------------------------------------------------------------------------------

class Normalizer(nn.Module, BaseNormalizer):
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

# -----------------------------------------------------------------------------------------------------------

class Singularity(BaseSingularity):
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
        self.print("SINGULARITY_INIT", device=self.device)

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

# -----------------------------------------------------------------------------------------------------------

class Universe(BaseUniverse):

    def __init__(self, config):
        """Initializes MilkyWay universe with configuration.

        Args:
            config (dict): Universe configuration dictionary.
        """
        self.config = config
        self.symbol = None
        self.timeframe = None
        self.after_ms = None
        self.until_ms = None
        self.limit = 1000000

        self._feature_table = None
        self._target_series = None
        self._feature_names = []
        self._discarded_dimensions = []  # Dropped non-numeric columns
        self._comets: Dict[str, Comet] = {}
        self._normalizers: Dict[str, Normalizer] = {}

        # Load features, filters, target
        self.features_to_request, self.filter_patterns, self.target_col = self._load_config()

    def _load_config(self):
        """Load universe configuration and initialize Comets and Normalizers.

        Returns:
            Tuple[List[str], List[str], str]: features_to_request, filter_patterns, target_col
        """
        # Trick to prevent circular imports
        from ml.space.comets.factory import CometFactory
        from ml.space.normalizers.factory import NormalizerFactory
        try:
            self.symbol, self.timeframe = self.config.get('fabric').get('matter').split('/', 1)
            self.after_ms = int(datetime.fromisoformat(str(self.config.get('fabric').get('after'))).timestamp() * 1000)
            self.until_ms = int(datetime.fromisoformat(str(self.config.get('fabric').get('until'))).timestamp() * 1000)

            self.print("SPACE_MATERIALIZING", name=type(self).__name__, symbol=self.symbol)

            # Initialize Comets
            for comet_name in self.config.get('comets'):
                self._comets[comet_name] = CometFactory.manifest(comet_name)

            # Initialize Normalizers
            for normalizer_name, normalizer_config in self.config.get('normalizers').items():
                is_disabled = str(normalizer_config.get('disabled', 'false')).strip().lower() in ('true', '1', 't', 'y', 'yes')
                if not is_disabled:
                    self._normalizers[normalizer_name] = NormalizerFactory.manifest(normalizer_name, normalizer_config)

            center = self.config.get('center', [])
            target = center[0] if isinstance(center, list) and center else None

            features = self.config.get('features', [])
            if target and target not in features:
                features.append(target)

            return features, self.config.get('filter', []), target
        except Exception as e:
            self.print("INITIALIZATION_FAILURE", e=e)
            raise

    def audit(self):
        """Print report of NaN and non-numeric columns.

        Returns:
            pd.DataFrame: DataFrame of columns with NaNs and their percentage.
        """
        if self._feature_table is None:
            self.print("UNINITIALIZED_RESOURCE_ERROR")
            return

        self.print("DIMENSIONAUDIT_REPORT")
        print("=" * 60)

        if self._discarded_dimensions:
            self.print("ATMOSPHERIC_WASTE", count = len(self._discarded_dimensions))
            for col in self._discarded_dimensions:
                print(f"   - {col}")
            print("-" * 60)
        else:
            self.print("NOSTRING_POLLUTION")

        nan_counts = self._feature_table.isna().sum()
        nan_percentages = (nan_counts / len(self._feature_table)) * 100
        void_report = pd.DataFrame({
            'void_count': nan_counts,
            'void_percent': nan_percentages
        }).query('void_count > 0').sort_values(by='void_count', ascending=False)

        if void_report.empty:
            self.print("MATTER_CHECK_SUCCESS", count=len(self._feature_names))
        else:
            self.print("VOID_REPORT_WARNING", count=len(void_report))
            print(void_report.to_string())
            critical = void_report[void_report['void_percent'] > 50]
            if not critical.empty:
                self.print("DATA_DENSITY_CRITICAL", count=len(critical))

        print("=" * 60)
        return void_report

    def bigbang(self) -> Tuple[pd.DataFrame, pd.Series]:
        """Apply normalization via all registered normalizers.

        Returns:
            Tuple[pd.DataFrame, pd.Series]: Normalized features and target series.
        """
        if self._feature_table is None:
            raise RuntimeError("Cannot Big Bang an unignited universe. Call ignite() first.")

        self.print("COSMIC_NORMALIZATION")

        current_names = list(self._feature_table.columns)
        normalized_tensor = torch.tensor(self._feature_table.values, dtype=torch.float32)

        for normalizer in self._normalizers.values():
            if hasattr(normalizer, 'generate_names'):
                current_names = normalizer.generate_names(current_names)
            normalized_tensor = normalizer.forward(normalized_tensor)

        self._feature_names = current_names
        self._feature_table = pd.DataFrame(
            normalized_tensor.cpu().numpy(),
            columns=self._feature_names,
            index=self._feature_table.index
        )

        self.audit()
        self.print("SPACE_BIG_BANG", dims=len(self._feature_names))
        return self._feature_table, self._target_series

    def dimensions(self):
        """Return shape of feature table.

        Returns:
            tuple: (rows, columns) of feature table or (0, 0) if uninitialized.
        """
        return self._feature_table.shape if self._feature_table is not None else (0, 0)

    def eject(self, filename: str, data: Any, is_model: bool = False, is_gene_dump: bool = False):
        """Deposit data into all registered comets.

        Args:
            filename (str): Name of file or checkpoint.
            data (Any): Payload to deposit.
            is_model (bool): Whether payload is a model checkpoint.
            is_gene_dump (bool): Whether payload is a gene dump.
        """
        for comet in self._comets.values():
            comet.deposit(filename, data, is_model, is_gene_dump)

    def features(self):
        """Return list of feature names."""
        return self._feature_names