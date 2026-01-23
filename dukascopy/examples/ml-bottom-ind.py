import pandas as pd, numpy as np, joblib, os
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
        "model_path": args[0] if len(args) > 0 else "GBP-USD-bottom-engine.pkl",
        "threshold": args[1] if len(args) > 1 else "0.59"
    }

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    # LOAD MODEL
    model_name = options.get('model_path', 'GBP-USD-bottom-engine.pkl')
    threshold = float(options.get('threshold', '0.59'))
    path = os.path.join(os.getcwd(), model_name)
    
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
    
    # 4. PREDICT
    probs = model.predict_proba(X) 
    class_map = {c: i for i, c in enumerate(model.classes_)}
    idx_bottom = class_map.get(1)

    confidence = np.zeros(len(df))
    signal = np.zeros(len(df))

    if idx_bottom is not None:
        confidence = probs[:, idx_bottom]
        
        # Component Extract
        hi, lo, op, cl = df['high'], df['low'], df['open'], df['close']
        
        # Get the total range of the candle
        total_range = hi - lo
        
        # Avoid div by zero
        safe_range = total_range.replace(0, 0.00001)

        # We find where the "Meat" (body) of the candle is located.
        # body_mid is the center point of the Open and Close.
        body_mid = (op + cl) / 2
        
        # Calculate how high the body sits relative to the total candle (0 to 1)
        # 1.0 = Body is at the very top (no upper wick)
        # 0.0 = Body is at the very bottom (no lower wick)
        relative_height = (body_mid - lo) / safe_range

        # The entire "Meat" of the candle must be in the upper 35% of the range.
        is_hammer = (relative_height > 0.65)
        
        # Green candle? Is close higher than open?
        is_green = cl > op

        # Now combine....
        # If AI says it's a bottom AND (Price action is UP OR Price action is a REJECTION)
        trigger = (confidence >= threshold) & (is_green | is_hammer)
        
        # Where trigger true, set signal to one, else zero
        signal = np.where(trigger, 1, 0)

    return pd.DataFrame({
        'confidence': confidence,
        'threshold': threshold, 
        'signal': signal
    }, index=df.index)