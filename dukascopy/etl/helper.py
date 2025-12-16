import copy
from dataclasses import asdict
from typing import Dict
import yaml

from config.app_config import AppConfig, ResampleConfig, ResampleSymbolOverride, ResampleSymbolTradingSession



def resample_get_sessions_for_symbol(symbol:str, app_config: AppConfig) -> Dict[str, ResampleSymbolTradingSession]:
    config = resample_get_symbol_config(symbol, app_config)

    if True:
        for key, session in config.sessions.items():
            print("="*80)
            print(f"Session({key}):")
            print("="*80)
            print(
                yaml.safe_dump(
                    asdict(session),
                    default_flow_style=False,
                    sort_keys=False,
                )
            )

    return config.sessions

def resample_get_symbol_config(symbol: str, app_config: AppConfig) -> ResampleSymbolOverride:
    """
    Generate a merged resample configuration for a specific symbol.

    This function starts from the global resample configuration and applies
    any symbol-specific overrides defined in `app_config.symbols`. Overrides
    may include:
        - round_decimals
        - batch_size
        - custom timeframes
        - skipped timeframes (absolute priority)
    """
    # Start with a deep copy of the global resample configuration so we never
    # mutate the original application config
    global_config: ResampleConfig = app_config.resample
    merged_config: ResampleConfig = copy.deepcopy(global_config)

    # Ensure a symbol override object always exists
    # This simplifies downstream logic by avoiding repeated None checks
    if not merged_config.symbols.get(symbol):
        merged_config.symbols.update({symbol: ResampleSymbolOverride()})

    # Retrieve the symbol-specific override (now guaranteed to exist)
    symbol_override: ResampleSymbolOverride = merged_config.symbols.get(symbol)

    # Apply symbol-level primitive overrides
    if symbol_override.round_decimals is None:
        symbol_override.round_decimals = merged_config.round_decimals 

    if symbol_override.batch_size is None:
        symbol_override.batch_size = merged_config.batch_size

    # Merge global timeframes with symbol-specific timeframes
    # Symbol timeframes override global ones with the same key
    base_timeframes = copy.deepcopy(merged_config.timeframes)
    base_timeframes.update(symbol_override.timeframes)
    merged_config.symbols.get(symbol).timeframes = base_timeframes

    # Handle session-specific overrides
    if symbol_override.sessions:
        # For each session, start from the global timeframes and apply
        # the session-specific timeframe overrides
        for ident, symbol_override_session in symbol_override.sessions.items():
            base_timeframes = copy.deepcopy(merged_config.timeframes)
            base_timeframes.update(symbol_override_session.timeframes)
            merged_config.symbols.get(symbol).sessions.get(ident).timeframes = base_timeframes
    else:
        # If no sessions are defined, create a default 24h session
        # that simply mirrors the symbol-level timeframes
        symbol_override.sessions = {
            "default": {
                "timeframes": merged_config.symbols.get(symbol).timeframes,
                "ranges": {
                    "default": {
                        "from": "00:00:00",
                        "to": "23:59:59"
                    }
                }
            }
        }

    # Apply skip_timeframes with absolute priority
    # Any skipped timeframe is removed from global, symbol, and session scopes
    if symbol_override.skip_timeframes:
        for timeframe_key in symbol_override.skip_timeframes:
            merged_config.timeframes.pop(timeframe_key, None)
            merged_config.symbols.get(symbol).timeframes.pop(timeframe_key, None)
            merged_config.symbols.get(symbol).sessions.get(ident).timeframes.pop(timeframe_key, None)

    return symbol_override
