# config.py

NUM_GENES = 24
POP_SIZE = 1200
HIDDEN_DIM = 64
LEARNING_RATE = 0.001
EPOCHS = 7 
GPU_CHUNK = 750  # VRAM safety threshold for 8GB

# FACTORY SPECS
OOS_BOUNDARY = 0.75         
STAGNANT_THRESHOLD = 50     
WEIGHT_MUTATION_RATE = 0.02
VITALITY_SOFTMAX_TEMP = 15.0
PRECISION_EXP = 6
WINDOW_FLOOR = 0.40         
LOOKBACK_WINDOW = 0.35      

# LOSS LOGIC
FOCAL_ALPHA = 0.99
FOCAL_GAMMA = 3.0

MIN_SIGNALS = 3         # NEW: Anti-dormancy floor

# DIVERSITY SPECS
MIN_REQUIRED_FAMILIES = 3
DIVERSITY_TARGETS = ['volume', 'volatility', 'trend', 'momentum']

GENE_FAMILIES = {
    'momentum': ['rsi', 'stoch', 'cmo', 'roc', 'williamsr', 'mfi'],
    'volatility': ['atr', 'bbands', 'width', 'keltner', 'volatility', 'donchian', 'natr'],
    'volume': ['adl', 'obv', 'volume', 'vwap', 'eom', 'pvi', 'nvi'],
    'trend': ['hurst', 'adx', 'psar', 'hma', 'ichimoku', 'sma', 'ema', 'macd', 'trix'],
    'statistical': ['entropy', 'pearson', 'autocorr', 'sharpe', 'rsquared', 'stddev']
}

BLACKLISTED_INDICATORS = [
    'zigzag*', 'swing-points*', 'fractaldimension*', 'kalman*', 
    'open', 'high', 'low', 'close', 'volume', 
    'is-open*', 'pivot*', 'camarilla-pivots*', 'psychlevels*', 
    'sma_*', 'midpoint*', 'drift*', 
    "*example-pivot-finder*", "*elliot*", "*macro*", "*fibonacci*", "feature*",
    'talib-cos*', 'talib-sin*', 'talib-tan*', 'talib-acos*', 'talib-asin*', 
    'talib-atan*', 'talib-mult*', 'talib-div*', 'talib-add*', 'talib-sub*', 
    'talib-sqrt*', 'talib-exp*', 'talib-ceil*', 'talib-floor*', 'talib-cosh*', 
    'talib-sinh*', 'talib-tanh*', 'talib-ln*', 'talib-log10*', 'talib-sqrt*',
    'talib-ht_dcperiod*', 'talib-ht_dcphase*', 'talib-ht_phasor*', 
    'talib-ht_sine*', 'talib-ht_trendline*', 'talib-ht_trendmode*',
    'talib-linearreg_intercept*', 'talib-linearreg_angle*',
    'talib-avgprice*', 'talib-medprice*', 'talib-typprice*', 'talib-wclprice*',
    'talib*', "example-multi-tf-rsi*"
]

FORCED_INDICATORS = [
    "example-multi-tf-rsi_EUR-USD_14_14_14_14",
    "example-multi-tf-rsi_DOLLAR.IDX-USD_14_14_14_14",
    "example-multi-tf-rsi_XAU-USD_14_14_14_14",
    "talib-cdl2crows", "talib-cdl3blackcrows", "talib-cdl3inside"
]

FORCED_GENES = [
    'example-multi-tf-rsi_EUR-USD_14_14_14_14__rsi1d',
    'example-multi-tf-rsi_EUR-USD_14_14_14_14__rsi1W',
    'example-multi-tf-rsi_DOLLAR.IDX-USD_14_14_14_14__rsi1d',
    'example-multi-tf-rsi_DOLLAR.IDX-USD_14_14_14_14__rsi1W',
    'example-multi-tf-rsi_XAU-USD_14_14_14_14__rsi1d',
    'example-multi-tf-rsi_XAU-USD_14_14_14_14__rsi1W'
]

CONFIG = {
    'BASE_URL': "http://localhost:8000/ohlcv/1.1",
    'SYMBOL': "EUR-USD",
    'TIMEFRAME': "4h",
    'TARGET_INDICATOR': "example-pivot-finder_50_bottoms",
    'START_DATE': "2021-01-01",
    'END_DATE': "2025-12-31",
    'LIMIT': 100000,
    'LOG_FILE': "alpha_factory_results.csv",
    'POP_SIZE': POP_SIZE,
    'GPU_CHUNK': GPU_CHUNK,
    'GENE_COUNT': NUM_GENES,
    'HIDDEN_DIM': HIDDEN_DIM,
    'LEARNING_RATE': LEARNING_RATE,
    'EPOCHS': EPOCHS,
    'FORCED_INDICATORS': FORCED_INDICATORS,
    'FORCED_GENES': FORCED_GENES,
    'BLACKLISTED_INDICATORS': BLACKLISTED_INDICATORS,
    'OOS_BOUNDARY': OOS_BOUNDARY,
    'STAGNANT_THRESHOLD': STAGNANT_THRESHOLD,
    'WEIGHT_MUTATION_RATE': WEIGHT_MUTATION_RATE,
    'VITALITY_SOFTMAX_TEMP': VITALITY_SOFTMAX_TEMP,
    'PRECISION_EXP': PRECISION_EXP,
    'WINDOW_FLOOR': WINDOW_FLOOR,
    'LOOKBACK_WINDOW': LOOKBACK_WINDOW,
    'FOCAL_ALPHA': FOCAL_ALPHA,
    'FOCAL_GAMMA': FOCAL_GAMMA,
    'MIN_REQUIRED_FAMILIES': MIN_REQUIRED_FAMILIES,
    'DIVERSITY_TARGETS': DIVERSITY_TARGETS,
    'GENE_FAMILIES': GENE_FAMILIES
}