import pandas as pd, numpy as np, joblib, os
from pathlib import Path
from typing import Dict, Any, List

_ENGINE_CACHE = {}

def description() -> str:
    return "ML Sniper: 2024-Tuned V-Bottom Detector"

def meta() -> Dict:
    return {"author": "Gemini", "version": 1.5, "verified": 1, "panel": 1}

def warmup_count(options: Dict[str, Any]) -> int:
    return 50

def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "model_path": args[0] if len(args) > 0 else "{symbol}-{timeframe}-engine.pkl",
        "threshold": args[1] if len(args) > 1 else "0.70"
    }

def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    from util.api import get_data
    
    # 1. SETUP & FETCH
    row = df.iloc[0]
    symbol, timeframe = row.symbol, row.timeframe
    after_ms, until_ms = int(row.time_ms), int(df.iloc[-1].time_ms)
    
    # CHANGED: Request RSI(7) to match the new 2024-Tuned Trainer
    # Indicators: ATR(14), SMA(50), RSI(7)
    indicators = ['atr_14', 'sma_50', 'rsi_7']
    df_ext = get_data(symbol, timeframe, after_ms, until_ms+1, len(df), "asc", indicators, {"disable_recursive_mapping": True})

    # Default Return if no data
    if df_ext is None or df_ext.empty:
        return pd.DataFrame({'confidence': 0, 'threshold': 0, 'signal': 0}, index=df.index)

    # 2. LOAD MODEL
    model_name = options.get('model_path', f"{symbol}-{timeframe}-engine.pkl").replace("{symbol}", symbol)
    threshold = float(options.get('threshold', '0.70'))
    
    path = os.path.join(Path(__file__).resolve().parent / "models", model_name)
    
    if path not in _ENGINE_CACHE:
        _ENGINE_CACHE[path] = joblib.load(path) if os.path.exists(path) else None
    
    model = _ENGINE_CACHE[path]
    if not model: 
        return pd.DataFrame({'confidence': 0, 'threshold': threshold, 'signal': 0}, index=df.index)

    # 3. FEATURE ENGINEERING (Strict 1:1 Match with the new Trainer)
    # Feature 1: Trend Deviation (Close vs SMA50)
    trend_dev = (df_ext['close'] - df_ext['sma_50']) / df_ext['close']
    
    # Feature 2: Normalized RSI (NOW USING RSI 7)
    rsi_norm = df_ext['rsi_7'] / 100.0
    
    # Feature 3: Volatility Ratio (ATR vs Close)
    vol_ratio = df_ext['atr_14'] / df_ext['close']
    
    # Feature 4: Body Strength (Candle Body vs ATR)
    body_strength = (df_ext['close'] - df_ext['open']) / df_ext['atr_14'].replace(0, 0.001)

    # 4. PREDICT
    # X Vector Order: [trend_dev, rsi_norm, vol_ratio, body_strength]
    X = np.column_stack([
        trend_dev.fillna(0),
        rsi_norm.fillna(0.5),
        vol_ratio.fillna(0),
        body_strength.fillna(0)
    ])
    
    # Get Consensus Confidence
    probs = model.predict_proba(X)
    idx_bottom = {c: i for i, c in enumerate(model.classes_)}.get(1)
    confidence = probs[:, idx_bottom] if idx_bottom is not None else np.zeros(len(df_ext))

    # 5. MAPPING RESULTS
    raw_results = pd.DataFrame({
        'time_ms': df_ext['time_ms'],
        'confidence': confidence,
        'threshold': threshold,
        'signal': np.where(confidence >= threshold, 1, 0)
    })

    # Merge back to ensure index alignment
    final_df = df[['time_ms']].merge(raw_results, on='time_ms', how='left')
    return final_df[['confidence', 'threshold', 'signal']].set_index(df.index).fillna(0)