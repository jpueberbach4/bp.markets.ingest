import glob
import os
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytz
import yaml


class ConfigLoader:
    def __init__(self, project_root: str = "."):
        self.project_root = project_root

    def load(self, config_path: str) -> Dict[str, Any]:
        """
        Loads a YAML file and recursively processes any 'includes' directives.
        """
        full_path = os.path.join(self.project_root, config_path)

        if not os.path.exists(full_path):
            raise FileNotFoundError(f"Configuration file not found: {full_path}")

        with open(full_path, 'r') as f:
            config = yaml.safe_load(f)

        return self._process_includes(config)

    def _process_includes(self, data: Any) -> Any:
        """
        Recursively traverses the configuration dictionary.
        If a dictionary contains an 'includes' list, it loads those files
        and merges them into the current dictionary level.
        """
        if isinstance(data, dict):
            # 1. Handle the 'includes' key if present
            if 'includes' in data and isinstance(data['includes'], list):
                included_files: List[str] = data.pop('includes')

                for pattern in included_files:
                    # Resolve the glob pattern relative to project root
                    glob_pattern = os.path.join(self.project_root, pattern)
                    matched_files = sorted(glob.glob(glob_pattern))

                    if not matched_files and '*' not in pattern:
                        print(f"Warning: Include file not found: {pattern}")

                    for file_path in matched_files:
                        with open(file_path, 'r') as f:
                            included_data = yaml.safe_load(f)
                            
                        # Recursively process includes inside the included file
                        included_data = self._process_includes(included_data)
                        
                        # Merge the included data into the current dictionary
                        self._deep_merge(data, included_data)

            # 2. Recursively process all other keys in the dictionary
            for key, value in data.items():
                data[key] = self._process_includes(value)

        elif isinstance(data, list):
            # Recurse into lists
            return [self._process_includes(item) for item in data]

        return data

    def _deep_merge(self, base: Dict[str, Any], update: Dict[str, Any]) -> None:
        """
        Merges 'update' into 'base' recursively.
        - Dictionaries are merged.
        - Lists are appended (extended).
        - Values are overwritten.
        """
        if not isinstance(update, dict):
            return

        for key, value in update.items():
            if key in base:
                if isinstance(base[key], dict) and isinstance(value, dict):
                    self._deep_merge(base[key], value)
                elif isinstance(base[key], list) and isinstance(value, list):
                    base[key].extend(value)
                else:
                    # Overwrite primitive values or mismatched types
                    base[key] = value
            else:
                base[key] = value


# Config loader
def _load_timezones_config() -> Dict[str, Any]:
    """Attempts to load the timezone configuration from the user or default yaml."""
    try:
        # ugly fix but high priority
        config_path = Path(__file__).parent.parent.parent.parent.parent
        config_file = config_path/'config.user.yaml' if Path(config_path/'config.user.yaml').exists() else config_path/"config.yaml"
        loader = ConfigLoader(project_root=".")
        full_config = loader.load(config_file)
        return full_config['transform']['timezones']
    except Exception as e:
        traceback.print_exc()
        raise Exception(f"Warning: Could not load config for is-open, drift and is-stale: {e}")

# Global cache variable
_TZ_CACHE = _load_timezones_config()

def _marketstate_backend_timezone_info_for_symbol(symbol: str) -> Tuple[str, Dict[str, Any]]:
    """
    Finds the timezone configuration for a given symbol.
    """
    global _TZ_CACHE
    
    for tz_name, tz_data in _TZ_CACHE.items():
        symbols = tz_data.get('symbols', [])
        
        # Handle wildcard or direct match
        if '*' in symbols or symbol in symbols:
            return tz_name, tz_data

    raise Exception(f"Error: Unknown timezone for {symbol}")


def _marketstate_backend_shift_for_symbol(symbol: str, ts_ms: int) -> int:
    """
    Determines the shift (ms) that WAS applied to a timestamp 
    based on the symbol's assigned timezone and the date.
    """
    target_tz_name, target_cfg = _marketstate_backend_timezone_info_for_symbol(symbol)
    
    try:
        # Convert timestamp (ms) to UTC datetime
        dt_utc = datetime.fromtimestamp(ts_ms / 1000, tz=pytz.utc)
        
        # Get target timezone
        target_tz = pytz.timezone(target_tz_name)
        
        # Create a naive noon time for that date, then localize it to the target timezone
        # This handles DST offsets correctly for that specific day
        dt_noon_naive = datetime(dt_utc.year, dt_utc.month, dt_utc.day, 12, 0, 0)
        tz_aware_dt = target_tz.localize(dt_noon_naive)
        
        # Calculate offset in minutes
        offset_minutes = int(tz_aware_dt.utcoffset().total_seconds() / 60)
        
        return target_cfg["offset_to_shift_map"].get(offset_minutes, 0)

    except Exception as e:
        raise Exception(f"Error in _marketstate_backend_shift_for_symbol: {e}")