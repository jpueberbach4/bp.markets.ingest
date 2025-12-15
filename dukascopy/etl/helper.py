import copy
from dataclasses import asdict
import yaml

from config.app_config import AppConfig, ResampleConfig, ResampleSymbolOverride, ResampleSymbolTradingSession



def resample_get_settings_for_symbol(symbol:str, app_config: AppConfig) -> Dict[str, ResampleSymbolTradingSession]:
    """
    This method emulates a Dict[str, ResampleSymbolTradingSession] 
    Even if no session is specified, it returns ResampleTradingSession Dictionary with the following
    
    - normalized from-to range (00:00->23:59) as shifted_time (from transform)
    - a list of timeframes

    If sessions are present for the symbol
    - normalizes the from-to-range based on timezone and as shifted_time (from transform)
    - returns immediately

    This will make it easier for the resample engine to handle it (one uniform dict[key, object]) which
    the resample engine can loop through.
    """
    pass


def resample_get_symbol_config(symbol: str, app_config: AppConfig) -> ResampleConfig:
    """
    Generate a merged resample configuration for a specific symbol.

    This function starts from the global resample configuration and applies
    any symbol-specific overrides defined in `app_config.symbols`. Overrides
    may include:
        - round_decimals
        - batch_size
        - custom timeframes
        - skipped timeframes (absolute priority)

    Parameters
    ----------
    symbol : str
        The trading symbol for which to generate the configuration (e.g., "BTC-USDT").
    app_config : AppConfig
        The root application configuration containing the global resample
        settings and any symbol-specific overrides.

    Returns
    -------
    ResampleConfig
        A new ResampleConfig instance with global settings merged with
        symbol-specific overrides.
    """
    # Start with global resample configuration
    global_config: ResampleConfig = app_config.resample
    merged_config: ResampleConfig = copy.deepcopy(global_config)

    # Check for symbol-specific overrides
    symbol_override: ResampleSymbolOverride = global_config.symbols.get(symbol)

    if symbol_override:

        # Override global round_decimals if specified
        if symbol_override.round_decimals is not None:
            merged_config.round_decimals = symbol_override.round_decimals

        # Override global batch_size if specified
        if symbol_override.batch_size is not None:
            merged_config.batch_size = symbol_override.batch_size

        # NOTE TO DEV: WE HAVE CHANGED A CRITICAL PART BELOW.
        #      DEFAULT RESAMPLE ENGINE DEPENDS ON ROOT TIMEFRAMES OBJECT
        #      RESAMPLE ENGINE WILL NEED TO CHECK IN DEEPEST LEVEL FIRST AND 
        #      THEN TRAVERSE UPWARDS, ALL THE WAY TO ROOT
        #      IE SESSION NOT EXIST, CHECK SYMBOL, IF NOT EXISTS, CHECK ROOT
        #      TODO: OPTIMIZE THE CODE BELOW
        
        # This symbol has SYMBOL-specific timeframes configured
        if symbol_override.timeframes:
            base_timeframes = copy.deepcopy(merged_config.timeframes)
            base_timeframes.update(symbol_override.timeframes)
            merged_config.symbols.get(symbol).timeframes = base_timeframes
            
            # If symbol.skip_timeframes is set, pop off the symbol-based timeframes that match
            if symbol_override.skip_timeframes:
                for timeframe_key in symbol_override.skip_timeframes:
                    merged_config.symbols.get(symbol).timeframes.pop(timeframe_key, None)

        # This symbol has SESSION-specific timeframes configured
        if symbol_override.sessions:
            # Extend session timeframes, using merged_config.timeframes as base
            # Basically: global.timeframes + symbol.timeframes + symbol.session.timeframes 
            for ident, symbol_override_session in symbol_override.sessions.items():
                base_timeframes = copy.deepcopy(merged_config.timeframes)
                base_timeframes.update(symbol_override_session.timeframes)
                merged_config.symbols.get(symbol).sessions.get(ident).timeframes = base_timeframes

                # If symbol.skip_timeframes is set, pop off the session-based timeframes that match
                # We dont support per-session skip_timeframes because thats a non-use-case
                if symbol_override.skip_timeframes:
                    for timeframe_key in symbol_override.skip_timeframes:
                        merged_config.symbols.get(symbol).sessions.get(ident).timeframes.pop(timeframe_key, None)

        # Remove any skipped timeframes (absolute priority)
        if symbol_override.skip_timeframes:
            for timeframe_key in symbol_override.skip_timeframes:
                merged_config.timeframes.pop(timeframe_key, None)

    if False:
        print(yaml.safe_dump(
            asdict(merged_config),
            default_flow_style=False,
            sort_keys=False,
        ))

    return merged_config