import unittest
import importlib.util
import os
import sys
from unittest.mock import patch
import pandas as pd

# Global list to track active signatures: (indicator, symbol, timeframe)
CALL_STACK = []

class TestIndicatorIntegrity(unittest.TestCase):
    def setUp(self):
        global CALL_STACK
        CALL_STACK = []

    def sync_parallel_mock(self, df, indicators, *args, **kwargs):
        """
        FORCE SYNCHRONOUS EXECUTION:
        Bypasses the thread pool so the recursion guard stays in the same thread.
        """
        from util.api import get_data
        
        # We manually iterate over indicators in the same thread
        for ind_name in indicators:
            # This will now correctly hit the trace_get_data spy
            get_data(
                symbol=df.iloc[0].symbol,
                timeframe=df.iloc[0].timeframe,
                indicators=[ind_name]
            )
        return df

    def trace_get_data(self, *args, **kwargs):
        """
        Stateful spy that detects recursive loops.
        """
        # Normalize arguments
        symbol = kwargs.get('symbol', args[0] if len(args) > 0 else "UNKNOWN")
        timeframe = kwargs.get('timeframe', args[1] if len(args) > 1 else "UNKNOWN")
        indicators = kwargs.get('indicators', args[6] if len(args) > 6 else [])

        for ind in indicators:
            signature = (ind, symbol, timeframe)
            
            # Trap
            if signature in CALL_STACK:
                path_str = " -> ".join([f"{i}[{s}/{t}]" for i, s, t in CALL_STACK])
                raise RecursionError(
                    f"Infinite loop detected: {ind} for {symbol}/{timeframe}!\n"
                    f"Chain: {path_str} -> {ind}[{symbol}/{timeframe}]"
                )
            
            # Push to stack and simulate the engine executing this sub-indicator
            CALL_STACK.append(signature)
            
            plugin_path = f"config.user/plugins/indicators/{ind}.py"
            if os.path.exists(plugin_path):
                # Unique module name per depth to bypass import caching
                mod_name = f"depth_{len(CALL_STACK)}_{ind}"
                spec = importlib.util.spec_from_file_location(mod_name, plugin_path)
                plugin = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(plugin)
                
                dummy_df = pd.DataFrame({
                    "time_ms": [1000], "close": [1.0],
                    "symbol": [symbol], "timeframe": [timeframe]
                })
                
                # RECURSIVE RE-ENTRY
                plugin.calculate(dummy_df, plugin.position_args([]))
            
            CALL_STACK.pop()
        
        return pd.DataFrame({
            "time_ms": [1000], "close": [1.0],
            "symbol": [symbol], "timeframe": [timeframe]
        })

    def test_all_plugins_for_loops(self):
        plugin_dir = "config.user/plugins/indicators"
        
        for filename in os.listdir(plugin_dir):
            if filename.endswith(".py") and not filename.startswith("__"):
                indicator_name = filename[:-3]
                
                # Patch get_data to track the stack
                # Patch parallel_indicators to stop thread-spawning
                with patch('util.api.get_data', side_effect=self.trace_get_data), \
                     patch('util.api.parallel_indicators', side_effect=self.sync_parallel_mock):
                    
                    global CALL_STACK
                    CALL_STACK = [(indicator_name, "EUR-USD", "1m")]
                    
                    # Load entry point plugin
                    file_path = os.path.join(plugin_dir, filename)
                    spec = importlib.util.spec_from_file_location("__entry__", file_path)
                    plugin = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(plugin)
                    
                    df = pd.DataFrame({
                        "time_ms": [1000], "close": [1.0],
                        "symbol": ["EUR-USD"], "timeframe": ["1m"]
                    })
                    
                    try:
                        plugin.calculate(df, plugin.position_args([]))
                    except RecursionError as e:
                        # This confirms the test catches the loop
                        # We use self.fail because we WANT to flag this as a broken indicator
                        self.fail(f"Infinite recursion detected in {indicator_name}!\n{e}")
                    except Exception as e:
                        self.fail(f"Indicator '{indicator_name}' crashed: {e}")

if __name__ == '__main__':
    unittest.main()