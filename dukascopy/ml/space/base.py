from abc import ABC, abstractmethod
from typing import Dict, Any
from pathlib import Path
import sys
import importlib
import random
import pandas as pd
import numpy as np
import os

# MESSAGING IMPORT BASED ON ENVIROMENT VARIABLE
log_style = os.getenv("ML_LOG_STYLE", "SPACEY").upper()
if log_style == "DEFAULT":
    module_path = "ml.space.messages.boring"
else:
    module_path = "ml.space.messages.spacey"

try:
    _module = importlib.import_module(module_path)
    STRING_TABLE = getattr(_module, "STRING_TABLE")
except (ImportError, AttributeError) as e:
    print(f"[Internal Error] Failed to load {module_path}: {e}")
    STRING_TABLE = {}

# END OF MESSAGING IMPORT

class Fabric(ABC):

    def print(self, key: str, **kwargs):
        """Ejects a string from the cosmic table with formatted parameters."""
        msg = STRING_TABLE.get(key, f"UNRESOLVED MATTER: {key}")
        print(msg.format(**kwargs))

class BaseComet(Fabric):
    pass

class BaseFlight(Fabric):
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

class BaseUniverse(Fabric):
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


class BaseFactory(Fabric):
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

class BaseLens(Fabric):
    pass

class BaseNormalizer(Fabric):
    pass

class BaseSingularity(Fabric):
    """
    Abstract predictive core.

    Responsible for training, inference,
    tensor conversion, and weight persistence.
    """

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

    @abstractmethod
    def save_state(self, path: str):
        """
        Persist model weights to disk.

        Args:
            path (str):
                Output file path.
        """
        pass


