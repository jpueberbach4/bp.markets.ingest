import unittest
from unittest.mock import MagicMock
from util.resolver import SelectionResolver
from util.dataclass import Dataset

class TestSelectionResolver(unittest.TestCase):
    def setUp(self):
        """Set up a mock environment with a variety of datasets."""
        self.mock_data = [
            self._create_mock_dataset("AAPL.US-USD", "15m", "/path/aapl_15m.bin"),
            self._create_mock_dataset("AAPL.US-USD", "1H", "/path/aapl_1h.bin"),
            self._create_mock_dataset("TSLA.US-USD", "15m", "/path/tsla_15m.bin"),
            self._create_mock_dataset("BTC-USD", "1D", "/path/btc_1d.bin"),
        ]
        self.resolver = SelectionResolver(self.mock_data)

    def _create_mock_dataset(self, symbol, tf, path):
        """Helper to build a mock Dataset object."""
        ds = MagicMock(spec=Dataset)
        ds.symbol = symbol
        ds.timeframe = tf
        ds.path = path
        ds.key = (symbol, tf)
        return ds

    def test_basic_resolution(self):
        """Test simple SYMBOL/TF resolution."""
        results, resolved = self.resolver.resolve(["AAPL.US-USD/15m"])
        self.assertEqual(len(results), 1)
        self.assertIn(("AAPL.US-USD", "15m"), resolved)
        self.assertEqual(results[0][0], "AAPL.US-USD")

    def test_wildcard_symbol_matching(self):
        """Test that '*' correctly matches multiple symbols."""
        results, _ = self.resolver.resolve(["*.US-USD/15m"])
        symbols = [r[0] for r in results]
        self.assertIn("AAPL.US-USD", symbols)
        self.assertIn("TSLA.US-USD", symbols)
        self.assertEqual(len(results), 2)

    def test_indicator_parsing_and_normalization(self):
        """Test bracket-aware indicator parsing and naming normalization."""
        results, _ = self.resolver.resolve(["BTC-USD[ema(20):rsi(14,2)]/1D"])
        indicators = results[0][4]
        self.assertEqual(indicators, ["ema_20", "rsi_14_2"])

    def test_comma_separated_timeframes(self):
        """Test resolving multiple timeframes for a single symbol."""
        results, _ = self.resolver.resolve(["AAPL.US-USD/15m,1H"])
        self.assertEqual(len(results), 2)
        timeframes = [r[1] for r in results]
        self.assertCountEqual(timeframes, ["15m", "1H"])

    def test_modifier_merging(self):
        """Test that global and local modifiers are merged correctly."""
        results, _ = self.resolver.resolve(["AAPL.US-USD:glob/15m:loc"])
        modifiers = results[0][3]
        self.assertIn("glob", modifiers)
        self.assertIn("loc", modifiers)

    def test_validation_failure_without_force(self):
        """Ensure an exception is raised for non-existent datasets."""
        with self.assertRaisesRegex(Exception, "Critical Error: Unresolved selections"):
            self.resolver.resolve(["MISSING/1D"], force=False)

    def test_validation_with_force(self):
        """Ensure force=True allows skipping missing datasets."""
        results, resolved = self.resolver.resolve(["MISSING/1D"], force=True)
        self.assertEqual(len(results), 0)
        self.assertEqual(len(resolved), 0)

if __name__ == "__main__":
    unittest.main()