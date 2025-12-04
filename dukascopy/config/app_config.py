from dataclasses import dataclass, field
from typing import Dict, List, Optional

@dataclass
class TimeframeConfig:
    """Configuration for a single resampled timeframe."""
    source: str
    rule: Optional[str] = None                                               # Resampling rule (e.g., '5T', '1H'). None for the base timeframe.
    label: Optional[str] = None                                              # 'left' or 'right'. None for the base timeframe.
    closed: Optional[str] = None                                             # 'left' or 'right'. None for the base timeframe.

#---

@dataclass
class ResamplePaths:
    """Directory paths used by the script."""
    data: str = "data/resample"                                              # Output directory

#---

@dataclass
class SymbolOverride:
    """Per-symbol configuration overrides."""
    round_decimals: Optional[int] = None                                    # Number of decimals to round to
    batch_size: Optional[int] = None                                        # How many lines to read in a single batch for this symbol
    timeframes: Dict[str, TimeframeConfig] = field(default_factory=dict)    # List of timeframes

#---

## Main Resample Configuration Dataclass

@dataclass
class ResampleConfig:
    """The root configuration for the resample.py script."""
    round_decimals: int = 8                                                 # Number of decimal to round to (default: 8)
    batch_size: int = 250000                                                # Number of lines to read in a single batch (250_000)
    paths: ResamplePaths = field(default_factory=ResamplePaths)             # Paths
    timeframes: Dict[str, TimeframeConfig] = field(default_factory=dict)    # List of timeframes
    symbols: Dict[str, SymbolOverride] = field(default_factory=dict)        # List of symbols

#---

## Root Configuration Dataclass

@dataclass
class AppConfig:
    """The root configuration for the entire application, holding all module configs."""
    resample: ResampleConfig = field(default_factory=ResampleConfig)