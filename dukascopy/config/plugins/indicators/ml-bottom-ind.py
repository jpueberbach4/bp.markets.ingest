import pandas as pd, numpy as np, joblib, os
from pathlib import Path
from typing import Dict, Any, List

_ENGINE_CACHE = {}

def description() -> str:
    return "ML Sniper: Random Forest AI Bottoms + Green Candle OR Rejection Confirmation (RSI Filtered)"

def meta() -> Dict:
    return {"author": "Google Gemini", "version": 200.0, "verified": 1, "panel": 1}

def warmup_count(options: Dict[str, Any]) -> int:
    return 50

def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "model_path": args[0] if len(args) > 0 else "{symbol}-{timeframe}-bottom-engine.pkl",
        "threshold": args[1] if len(args) > 1 else "0.59"
    }

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    # LOAD MODEL
    model_name = options.get('model_path', 'GBP-USD-bottom-engine.pkl')
    threshold = float(options.get('threshold', '0.59'))
    path = os.path.join(Path(__file__).resolve().parent / "models", model_name)
    
    if path not in _ENGINE_CACHE:
        if os.path.exists(path): 
            _ENGINE_CACHE[path] = joblib.load(path)
        else:
            return pd.DataFrame({'confidence': 0, 'signal': 0}, index=df.index)
    
    model = _ENGINE_CACHE[path]

    # INDICATORS
    sma50 = df['close'].rolling(50).mean()
    tr = pd.concat([(df['high']-df['low']), (df['high']-df['close'].shift(1)).abs(), (df['low']-df['close'].shift(1)).abs()], axis=1).max(axis=1)
    atr = tr.ewm(com=13, adjust=False).mean()
    
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).ewm(com=13, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(com=13, adjust=False).mean()
    rsi = 100 - (100 / (1 + (gain / loss.replace(0, np.nan))))

    # FEATURES (4-Feature Set)
    dist_50 = (df['close'] - sma50) / df['close']
    rsi_norm = rsi / 100.0
    vol_ratio = atr / df['close']
    safe_atr = atr.replace(0, 0.00001)
    body_strength = (df['close'] - df['open']) / safe_atr

    X = np.column_stack([
        dist_50.fillna(0), 
        rsi_norm.fillna(0), 
        vol_ratio.fillna(0),
        body_strength.fillna(0)
    ])
    
    # PREDICT
    probs = model.predict_proba(X) 
    class_map = {c: i for i, c in enumerate(model.classes_)}
    idx_bottom = class_map.get(1)

    confidence = np.zeros(len(df))
    signal = np.zeros(len(df))

    if idx_bottom is not None:
        confidence = probs[:, idx_bottom]
        
        # Geometry Calculations
        hi, lo, op, cl = df['high'], df['low'], df['open'], df['close']
        total_range = hi - lo
        safe_range = total_range.replace(0, 0.00001)
        body_size = np.abs(cl - op)
        body_mid = (op + cl) / 2
        relative_height = (body_mid - lo) / safe_range

        # Pattern Detection
        is_doji = (body_size <= (total_range * 0.38)) & (total_range > 0)
        
        is_dragonfly   = is_doji & (relative_height > 0.90)
        is_gravestone  = is_doji & (relative_height < 0.10)
        is_long_legged = is_doji & (relative_height > 0.40) & (relative_height < 0.60)
        is_hammer      = (relative_height > 0.60)
        is_green       = (cl > op)

        # Dynamic Threshold Trapping
        # We start with a very high "impossible" threshold and lower it per pattern
        needed_conf = np.full(len(df), 0.70) # "is_any" fallback

        # Apply specific thresholds (Order matters: more specific patterns last)
        needed_conf = np.where(is_green,       threshold,    needed_conf)
        needed_conf = np.where(is_gravestone,  0.63,         needed_conf)
        needed_conf = np.where(is_hammer,      0.55,         needed_conf)
        needed_conf = np.where(is_long_legged, 0.53,         needed_conf)
        needed_conf = np.where(is_dragonfly,   0.52,         needed_conf)

        # Signal if the AI confidence for THIS specific row exceeds 
        # the required threshold for the pattern found on THIS specific row.
        trigger = (confidence >= (needed_conf - 0.000001))
        
        signal = np.where(trigger, 1, 0)

    return pd.DataFrame({
        'confidence': confidence,
        'threshold': threshold, 
        'relative-height':relative_height,
        #'is_doji': is_doji,
        'signal': signal
    }, index=df.index)