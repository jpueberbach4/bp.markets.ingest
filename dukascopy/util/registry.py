from util.dataclass import Dataset
from typing import List, Optional

class DatasetRegistry:
    def __init__(self, datasets: List[Dataset]):
        # Internal structure: { 'SYMBOL': { 'TIMEFRAME': Dataset } }
        self._lookup = {}
        self._datasets = datasets
        self._index_datasets(datasets)

    def _index_datasets(self, datasets: List[Dataset]):
        """Builds a nested dictionary for fast access."""
        for ds in datasets:
            if ds.symbol not in self._lookup:
                self._lookup[ds.symbol] = {}
            self._lookup[ds.symbol][ds.timeframe] = ds

    def find(self, symbol: str, timeframe: str) -> Optional[Dataset]:
        return self._lookup.get(symbol, {}).get(timeframe)

    def get_available_datasets(self):
        return self._datasets

    def get_available_timeframes(self, symbol: str) -> List[str]:
        """Returns all timeframes available for a specific symbol."""
        return list(self._lookup.get(symbol, {}).keys())