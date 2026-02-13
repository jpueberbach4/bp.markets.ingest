import os
import talib
from talib import abstract
import sys
import glob

# Configuration
OUTPUT_DIR = "config.user/plugins/indicators"

# We have the following already as pure Polars (fast-path) indicators.
EXCLUDE_INDICATORS = [
    'acos', 'asin', 'adx', 'aroon', 'atr', 'atrp', 'bbands', 'cci', 
    'cmo', 'chaikin', 'ema', 'eom', 'macd', 'midpoint', 'mfi', 'obv', 
    'psar', 'roc', 'rsi', 'sma', 'stddev', 'stoch', 'ultosc', 'willr', 'wma'
]

TEMPLATE = """import pandas as pd
import numpy as np
import polars as pl
import talib
from talib import abstract
from typing import List, Dict, Any

def description() -> str:
    return "TA-Lib {name}: {display_name} ({group})"

def meta() -> Dict:
    return {{
        "author": "TA-Lib Autogen",
        "version": 1.3,
        "panel": {panel_id},
        "verified": 1,
        "talib-validated": 1,
        "polars": 0
    }}

def warmup_count(options: Dict[str, Any]) -> int:
    periods = [int(v) for k, v in options.items() if 'period' in k.lower()]
    if periods:
        return max(periods) * 3
    return {default_warmup}

def position_args(args: List[str]) -> Dict[str, Any]:
    return {{
{position_args_body}
    }}

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    raise NotImplementedError("Polars native path not yet auto-generated for {name}")

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    inputs = {{
        'open': df['open'],
        'high': df['high'],
        'low': df['low'],
        'close': df['close'],
        'volume': df['volume']
    }}

    param_types = {param_types_literal}
    clean_opts = {{}}
    
    for k, v in options.items():
        if k in param_types:
            try:
                clean_opts[k] = param_types[k](v)
            except (ValueError, TypeError):
                clean_opts[k] = v
        else:
            clean_opts[k] = v

    try:
        func = abstract.Function('{name}')
        res = func(inputs, **clean_opts)
    except Exception:
        res = None

    # Handle Multi-output indicators
    output_names = {output_names_literal}

    if res is None or (isinstance(res, (np.ndarray, list, tuple)) and len(res) == 0):
        if output_names:
             return pd.DataFrame(np.nan, index=df.index, columns=output_names)
        return pd.DataFrame(np.nan, index=df.index, columns=['{name}'])

    if isinstance(res, (tuple, list)):
        if len(res) == len(output_names):
            data = {{name: arr for name, arr in zip(output_names, res)}}
            return pd.DataFrame(data, index=df.index)
            
        # Fix: use output_names variable and f-string escaping correctly
        cols = [f"output_{{i}}" for i in range(len(res))]
        return pd.DataFrame(list(res), index=range(len(res))).T.set_index(df.index).set_axis(cols, axis=1)

    if isinstance(res, pd.DataFrame):
        return res
    if isinstance(res, pd.Series):
        return res.to_frame(name='{name}')

    return pd.DataFrame(res, columns=['{name}'], index=df.index)
"""

def generate():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    print(f"Cleaning old plugins in {OUTPUT_DIR}...")
    for f in glob.glob(os.path.join(OUTPUT_DIR, "talib-*.py")):
        os.remove(f)

    print(f"Scanning TA-Lib...")
    try:
        functions = talib.get_functions()
    except Exception:
        sys.exit(1)
    
    success_count = 0
    
    for name in functions:
        if name.lower() in EXCLUDE_INDICATORS:
            continue

        try:
            func_obj = abstract.Function(name)
            info = func_obj.info
            
            panel_id = 0 if info['group'] == 'Overlap Studies' else 1
            params = info.get('parameters', {})
            output_names = info.get('output_names', [])
            
            param_types_dict = {}
            for k, default_val in params.items():
                if isinstance(default_val, float):
                    param_types_dict[k] = "float"
                elif isinstance(default_val, int):
                    param_types_dict[k] = "int"
                else:
                    param_types_dict[k] = "str"
            
            param_types_literal = "{" + ", ".join([f'"{k}": {v}' for k, v in param_types_dict.items()]) + "}"

            args_lines = []
            for idx, (key, default_val) in enumerate(params.items()):
                line = f'        "{key}": args[{idx}] if len(args) > {idx} else "{default_val}"'
                args_lines.append(line)
            position_args_body = ",\n".join(args_lines) or "        # No parameters"

            default_warmup = 30
            if 'timeperiod' in params:
                default_warmup = params['timeperiod'] * 3

            content = TEMPLATE.format(
                name=name,
                display_name=info['display_name'],
                group=info['group'],
                panel_id=panel_id,
                default_warmup=default_warmup,
                position_args_body=position_args_body,
                output_names_literal=str(output_names),
                param_types_literal=param_types_literal
            )
            
            with open(os.path.join(OUTPUT_DIR, f"talib-{name.lower()}.py"), "w") as f:
                f.write(content)
            success_count += 1
            
        except Exception as e:
            print(f"Failed {name}: {e}")

    print(f"Done. {success_count} plugins generated.")

if __name__ == "__main__":
    generate()