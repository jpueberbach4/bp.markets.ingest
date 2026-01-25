import unittest
from unittest.mock import patch, MagicMock
import os
from util.discovery import DataDiscovery
from util.dataclass import Dataset

class TestDataDiscovery(unittest.TestCase):
    def setUp(self):
        """Set up mock configuration and DataDiscovery instance."""
        self.mock_config = MagicMock()
        self.mock_config.paths.data = "/fake/data"
        self.mock_config.fmode = "binary"
        
        with patch('os.path.isdir', return_value=True):
            self.discovery = DataDiscovery(self.mock_config)

    @patch('os.path.abspath')
    @patch('os.path.isdir')
    @patch('os.scandir')
    def test_scan_datasets(self, mock_scandir, mock_isdir, mock_abspath):
        """Test the scan method to ensure it finds and sorts datasets."""
        
        mock_isdir.return_value = True
        mock_abspath.side_effect = lambda x: x

        tf_entry = MagicMock()
        tf_entry.is_dir.return_value = True
        tf_entry.name = "15m"
        tf_entry.path = "/fake/data/resample/15m"

        file_entry = MagicMock()
        file_entry.is_file.return_value = True
        file_entry.name = "AAPL.US-USD.bin"

        def scandir_side_effect(path):
            if "resample" in path and "15m" not in path:
                return [tf_entry]
            if "15m" in path or "aggregate/1m" in path:
                return [file_entry]
            return []

        mock_scandir.side_effect = lambda path: MagicMock(
            __enter__=lambda s: scandir_side_effect(path),
            __exit__=MagicMock()
        )

        datasets = self.discovery.scan()

        self.assertIsInstance(datasets, list)
        self.assertTrue(len(datasets) > 0)
        
        self.assertEqual(datasets[0].symbol, "AAPL.US-USD")
        
        timeframes = [d.timeframe for d in datasets]
        self.assertIn("1m", timeframes)
        self.assertIn("15m", timeframes)

    def test_scan_no_data_dir(self):
        """Test that scan returns an empty list if base data directory is missing."""
        with patch('os.path.isdir', return_value=False):
            datasets = self.discovery.scan()
            self.assertEqual(datasets, [])

if __name__ == "__main__":
    unittest.main()