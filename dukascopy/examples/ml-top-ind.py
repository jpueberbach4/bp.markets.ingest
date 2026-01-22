import pandas as pd, numpy as np, joblib, os
from typing import Dict, Any, List

_ENGINE_CACHE = {}


_ENGINE_CACHE = {}

def description() -> str:
    return "ML Sniper: Random Forest AI TOP + Red Candle Confirmation (RSI Filtered)"

def meta() -> Dict:
    return {"author": "Google Gemini", "version": 200.0, "verified": 1, "panel": 1}

def warmup_count(options: Dict[str, Any]) -> int:
    return 50

def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "model_path": args[0] if len(args) > 0 else "GBP-USD-top-engine.pkl",
        "threshold": args[1] if len(args) > 1 else "0.55"
    }

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    model_name = options.get('model_path', 'GBP-USD-top-engine.pkl')
    threshold = float(options.get('threshold', '0.55'))
    path = os.path.join(os.getcwd(), model_name)
    
    if path not in _ENGINE_CACHE:
        if os.path.exists(path): _ENGINE_CACHE[path] = joblib.load(path)
        else: return pd.DataFrame({'confidence': 0, 'signal': 0}, index=df.index)
    
    model = _ENGINE_CACHE[path]

    # Indicators
    sma50 = df['close'].rolling(50).mean()
    tr = pd.concat([(df['high']-df['low']), (df['high']-df['close'].shift(1)).abs(), (df['low']-df['close'].shift(1)).abs()], axis=1).max(axis=1)
    atr = tr.ewm(com=13, adjust=False).mean()
    
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).ewm(com=13, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(com=13, adjust=False).mean()
    rsi = 100 - (100 / (1 + (gain / loss.replace(0, np.nan))))

    # Features
    dist_50 = (df['close'] - sma50) / df['close']
    rsi_norm = rsi / 100.0
    vol_ratio = atr / df['close']
    body_strength = (df['close'] - df['open']) / atr.replace(0, 0.00001)

    X = np.column_stack([dist_50.fillna(0), rsi_norm.fillna(0), vol_ratio.fillna(0), body_strength.fillna(0)])
    
    probs = model.predict_proba(X) 
    idx_top = {c: i for i, c in enumerate(model.classes_)}.get(1)

    confidence = np.zeros(len(df))
    signal = np.zeros(len(df))

    if idx_top is not None:
        confidence = probs[:, idx_top]
        # TOP LOGIC: Confidence + Overbought RSI + Red Candle
        signal[(confidence > threshold) & (rsi > 60) & (body_strength < 0)] = 1

    return pd.DataFrame({'confidence': confidence, 'signal': signal, 'threshold': threshold}, index=df.index)