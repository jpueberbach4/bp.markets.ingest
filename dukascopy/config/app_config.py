from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class TimeframeConfig:
    """Configuration for a single resampled timeframe."""
    # Resampling rule (e.g., '5T', '1H'). None for the base timeframe.
    rule: Optional[str] = None
    # Label for interval alignment ('left' or 'right'). None for base timeframe.
    label: Optional[str] = None
    # Whether intervals are closed on the 'left' or 'right'. None for base timeframe.
    closed: Optional[str] = None
    # Source timeframe key or identifier.
    source: str = ""


@dataclass
class ResamplePaths:
    """Directory paths used by the script."""
    # Output directory for resampling results.
    data: str = "data/resample"


@dataclass
class SymbolOverride:
    """Per-symbol configuration overrides."""
    # Number of decimals to round to.
    round_decimals: Optional[int] = None
    # Number of lines to read per batch for this symbol.
    batch_size: Optional[int] = None
    # Mapping: timeframe name -> timeframe config.
    timeframes: Dict[str, TimeframeConfig] = field(default_factory=dict)


@dataclass
class ResampleConfig:
    """The root configuration for the resample.py script."""
    round_decimals: int = 8
    batch_size: int = 250_000
    paths: ResamplePaths = field(default_factory=ResamplePaths)
    # Mapping: timeframe name -> timeframe config.
    timeframes: Dict[str, TimeframeConfig] = field(default_factory=dict)
    # Mapping: symbol name -> symbol-specific overrides.
    symbols: Dict[str, SymbolOverride] = field(default_factory=dict)


@dataclass
class AppConfig:
    """The root configuration for the entire application."""
    resample: ResampleConfig = field(default_factory=ResampleConfig)
