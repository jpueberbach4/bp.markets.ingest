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
            print(f"{symbol} => Session({key}):")
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
    Build and return the fully merged resample configuration for a single symbol.

    The merge order is:
        1. Global resample configuration
        2. Symbol-level overrides
        3. Session-level overrides
        4. skip_timeframes (absolute priority, applied last)

    The returned object is a ResampleSymbolOverride containing resolved
    primitives, timeframes, and sessions ready for consumption by the
    resampling engine.

    Parameters
    ----------
    symbol : str
        Trading symbol identifier (e.g. "AUS.IDX-AUD").
    app_config : AppConfig
        Root application configuration.

    Returns
    -------
    ResampleSymbolOverride
        The resolved symbol configuration including session-aware timeframes.
    """
    # Copy the global resample configuration to avoid mutating the source config
    global_config: ResampleConfig = app_config.resample
    merged_config: ResampleConfig = copy.deepcopy(global_config)

    # Ensure a symbol override always exists to simplify merge logic
    if not merged_config.symbols.get(symbol):
        merged_config.symbols.update({symbol: ResampleSymbolOverride()})

    # Fetch the symbol override instance
    symbol_override: ResampleSymbolOverride = merged_config.symbols.get(symbol)

    # Resolve primitive overrides, falling back to global defaults
    symbol_override.round_decimals = (
        symbol_override.round_decimals or merged_config.round_decimals
    )
    symbol_override.batch_size = (
        symbol_override.batch_size or merged_config.batch_size
    )

    # Build the symbol-level timeframe set:
    # global timeframes first, symbol overrides on top
    base_timeframes = copy.deepcopy(merged_config.timeframes)
    base_timeframes.update(symbol_override.timeframes)
    symbol_override.timeframes = base_timeframes

    # Merge session-specific timeframes on top of symbol-level timeframes
    if symbol_override.sessions:
        for ident, session in symbol_override.sessions.items():
            # Start from the fully resolved symbol timeframes
            s_timeframes = copy.deepcopy(symbol_override.timeframes)
            # Apply session-specific overrides
            s_timeframes.update(session.timeframes)
            # Persist the merged result back into the session
            session.timeframes = s_timeframes
    else:
        # Create a default 24h session if none are defined
        from config.app_config import (
            ResampleSymbolTradingSession,
            ResampleSymbolTradingSessionRange,
        )

        default_range = ResampleSymbolTradingSessionRange(
            from_time="00:00:00",
            to_time="23:59:59",
        )
        default_session = ResampleSymbolTradingSession(
            timeframes=copy.deepcopy(symbol_override.timeframes),
            ranges={"default": default_range},
        )
        symbol_override.sessions = {"default": default_session}

    # Apply skip_timeframes with absolute priority across all scopes
    if symbol_override.skip_timeframes:
        for tf_key in symbol_override.skip_timeframes:
            # Remove from global view
            merged_config.timeframes.pop(tf_key, None)
            # Remove from symbol-level view
            symbol_override.timeframes.pop(tf_key, None)
            # Remove from all session-level views
            for session in symbol_override.sessions.values():
                session.timeframes.pop(tf_key, None)

    return symbol_override
