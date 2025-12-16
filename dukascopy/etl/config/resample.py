import copy
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict

from config.app_config import AppConfig, ResampleConfig, ResampleSymbol, \
                         ResampleTimeframe, ResampleSymbolTradingSession, \
                         ResampleSymbolTradingSessionRange


import copy
from typing import Dict, List, Optional
from dataclasses import dataclass, field

def resample_get_symbol_config(symbol: str, app_config: AppConfig) -> ResampleSymbol:
    # 1. Create a deep copy of global config to prevent accidental mutations of original settings
    merged_config: ResampleConfig = copy.deepcopy(app_config.resample)

    # 2. Initialize a blank ResampleSymbol object if the requested symbol isn't in the config
    if symbol not in merged_config.symbols:
        merged_config.symbols[symbol] = ResampleSymbol()

    symbol_override = merged_config.symbols[symbol]

    # 3. Apply global defaults to symbol primitives if symbol-specific values are missing
    symbol_override.round_decimals = symbol_override.round_decimals or merged_config.round_decimals
    symbol_override.batch_size = symbol_override.batch_size or merged_config.batch_size

    # 4. Build the base timeframe set for the symbol by merging Global TFs with Symbol TFs
    base_tfs = copy.deepcopy(merged_config.timeframes)
    for tf_name, tf_val in symbol_override.timeframes.items():
        # Handle case where YAML loader provides raw dicts instead of dataclass instances
        if isinstance(tf_val, dict):
            tf_val = ResampleTimeframe(**tf_val)
        base_tfs[tf_name] = tf_val
    symbol_override.timeframes = base_tfs

    # 5. Determine trading session logic
    if not symbol_override.sessions:
        # If no session is defined, default to a 24-hour window using the symbol's base TFs
        default_range = ResampleSymbolTradingSessionRange(from_time="00:00:00", to_time="23:59:59")
        symbol_override.sessions = {
            "default": ResampleSymbolTradingSession(
                ranges={"default": default_range},
                timeframes=copy.deepcopy(symbol_override.timeframes)
            )
        }
    else:
        # If sessions exist, ensure each session inherits the symbol's base TFs + session-level overrides
        for sess_name, session in symbol_override.sessions.items():
            s_tfs = copy.deepcopy(symbol_override.timeframes)
            for tf_name, tf_val in session.timeframes.items():
                if isinstance(tf_val, dict):
                    tf_val = ResampleTimeframe(**tf_val)
                s_tfs[tf_name] = tf_val
            session.timeframes = s_tfs

    # 6. Cleanup: Remove specific timeframes explicitly listed in 'skip_timeframes'
    for ident in symbol_override.skip_timeframes:
        for sess_name, session in symbol_override.sessions.items():
            # Remove from individual sessions
            session.timeframes.pop(ident, None)
        # Remove from the symbol-level base timeframe map
        symbol_override.timeframes.pop(ident, None)

    return symbol_override