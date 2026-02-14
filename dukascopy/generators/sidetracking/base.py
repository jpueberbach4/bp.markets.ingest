import abc
import yaml
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

@dataclass
class TimeWindowAction:
    """Represents a single configuration block for a specific time range."""
    id: str
    action: str             # "+", "-", "*", "/"
    columns: List[str]
    value: float
    from_date: datetime
    to_date: datetime

class IAdjustmentStrategy(abc.ABC):
    """
    Strict Interface for implementing corporate actions (Panama, Splits, Dividends).
    """

    @abc.abstractmethod
    def fetch_data(self, symbol: str) -> List[Dict[str, Any]]:
        """
        Connects to external datasource and returns a normalized list of events.
        """
        pass

    @abc.abstractmethod
    def generate_config(self, symbol: str, raw_data: List[Dict[str, Any]]) -> List[TimeWindowAction]:
        """
        Calculates the specific windows and values based on the raw data.
        """
        pass

class ConfigGenerator:
    """
    Context class that uses a strategy to build the final YAML.
    """
    def __init__(self, strategy: IAdjustmentStrategy):
        self.strategy = strategy

    def build_yaml(self, symbol: str, source_name: str) -> str:
        # Execute Remote Fetch
        data = self.strategy.fetch_data(source_name)
        
        if not data:
            return f"# No data found or error occurred for {source_name}"

        # Execute Math/Logic
        window_actions = self.strategy.generate_config(source_name, data)
        
        # Serialize to Dictionary
        post_processors = {}
        for act in window_actions:
            post_processors[act.id] = {
                "action": act.action,
                "columns": act.columns,
                "value": act.value,
                "from_date": act.from_date.strftime("%Y-%m-%d %H:%M:%S"),
                "to_date": act.to_date.strftime("%Y-%m-%d %H:%M:%S")
            }

        final_config = {
            f"{symbol}": {
                "source": source_name,
                "post": post_processors
            }
        }

        # Return YAML string
        return yaml.dump(final_config, sort_keys=False)