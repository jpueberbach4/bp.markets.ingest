import unittest
from unittest.mock import MagicMock
from util.registry import DatasetRegistry
from util.dataclass import Dataset

class TestDatasetRegistry(unittest.TestCase):
    def setUp(self):
        """Set up a fresh registry with mock datasets before each test."""
        # Create mock Dataset instances
        self.ds1 = MagicMock(spec=Dataset)
        self.ds1.symbol = "AAPL.US-USD"
        self.ds1.timeframe = "15m"
        self.ds1.path = "/data/resample/15m/AAPL.US-USD.bin"

        self.ds2 = MagicMock(spec=Dataset)
        self.ds2.symbol = "AAPL.US-USD"
        self.ds2.timeframe = "1H"
        self.ds2.path = "/data/resample/1H/AAPL.US-USD.bin"

        self.ds3 = MagicMock(spec=Dataset)
        self.ds3.symbol = "TSLA.US-USD"
        self.ds3.timeframe = "15m"
        self.ds3.path = "/data/resample/15m/TSLA.US-USD.bin"

        # Initialize registry with the mock list
        self.datasets = [self.ds1, self.ds2, self.ds3]
        self.registry = DatasetRegistry(self.datasets)

    def test_find_existing_dataset(self):
        """Test retrieving a dataset that exists in the registry."""
        result = self.registry.find("AAPL.US-USD", "15m")
        self.assertEqual(result, self.ds1)
        self.assertEqual(result.path, "/data/resample/15m/AAPL.US-USD.bin")

    def test_find_non_existent_symbol(self):
        """Test finding a symbol that isn't in the registry."""
        result = self.registry.find("NONEXISTENT", "15m")
        self.assertIsNone(result)

    def test_find_non_existent_timeframe(self):
        """Test finding a valid symbol with an invalid timeframe."""
        result = self.registry.find("AAPL.US-USD", "1D")
        self.assertIsNone(result)

    def test_get_available_datasets(self):
        """Test that all registered datasets are returned."""
        available = self.registry.get_available_datasets()
        self.assertEqual(len(available), 3)
        self.assertIn(self.ds1, available)
        self.assertIn(self.ds3, available)

    def test_get_available_timeframes(self):
        """Test retrieving all timeframes for a specific symbol."""
        tfs = self.registry.get_available_timeframes("AAPL.US-USD")
        self.assertCountEqual(tfs, ["15m", "1H"])

    def test_get_timeframes_for_invalid_symbol(self):
        """Test getting timeframes for a symbol that doesn't exist."""
        tfs = self.registry.get_available_timeframes("INVALID")
        self.assertEqual(tfs, [])

if __name__ == "__main__":
    unittest.main()