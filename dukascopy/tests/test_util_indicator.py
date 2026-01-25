import unittest
from unittest.mock import patch, MagicMock
import stat
from pathlib import Path
from util.indicator import IndicatorRegistry

class TestIndicatorRegistry(unittest.TestCase):
    def setUp(self):
        """Set up mock configuration and instance."""
        self.mock_config = MagicMock()
        self.mock_config.paths.data = "/fake/data"
        
        with patch.object(IndicatorRegistry, 'load_all_plugins', return_value={}):
            self.mgr = IndicatorRegistry(self.mock_config)
            
            self.mgr.core_dir = Path("util/plugins/indicators")
            self.mgr.user_dir = Path("/fake/user/plugins")

    def test_get_maximum_warmup_rows(self):
        """Test calculation logic using a manually populated registry."""
        mock_sma = MagicMock()
        mock_sma.__globals__ = {"warmup_count": lambda opts: 20}
        
        self.mgr.registry = {'sma': {'calculate': mock_sma}}
        
        warmup = self.mgr.get_maximum_warmup_rows(["sma_20"])
        self.assertEqual(warmup, 20)

    @patch('pathlib.Path.stat')
    @patch('os.listdir')
    @patch('importlib.util.spec_from_file_location')
    @patch('importlib.util.module_from_spec')
    def test_load_all_plugins_logic(self, mock_mod_spec, mock_spec, mock_listdir, mock_path_stat):
        """Test discovery logic by directly patching pathlib.Path.stat."""
        
        def listdir_side_effect(path):
            if "util/plugins/indicators" in str(path):
                return ['sma.py']
            return []
        
        mock_listdir.side_effect = listdir_side_effect
        
        mock_stat_obj = MagicMock()
        mock_stat_obj.st_mtime = 999.0
        mock_stat_obj.st_size = 100
        mock_stat_obj.st_mode = stat.S_IFREG 
        
        mock_path_stat.return_value = mock_stat_obj

        mock_module = MagicMock()
        mock_module.calculate = lambda x: x
        mock_mod_spec.return_value = mock_module

        plugins = self.mgr.load_all_plugins()

        self.assertIn('sma', plugins)
        self.assertEqual(plugins['sma']['mtime'], 999.0)

    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.stat')
    def test_refresh_skips_unchanged_files(self, mock_path_stat, mock_path_exists):
        """Verify that reload is skipped if mtime/size are identical."""
        
        mock_path_exists.return_value = True

        self.mgr.registry = {'sma': {'mtime': 500.0, 'size': 1000}}
        
        mock_stat_obj = MagicMock()
        mock_stat_obj.st_mtime = 500.0
        mock_stat_obj.st_size = 1000
        mock_path_stat.return_value = mock_stat_obj

        indicators = ['sma']

        with patch('importlib.util.spec_from_file_location') as mock_spec:
            self.mgr.refresh(indicators)
            mock_spec.assert_not_called()

if __name__ == "__main__":
    unittest.main()