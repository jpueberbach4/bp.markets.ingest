import polars as pl
import pandas as pd
from typing import List, Dict, Any

def description() -> str:
    """
    Returns a human-readable description for the API and UI.
    """
    return (
        "Standard Deviation is a statistical measure of market volatility. It "
        "quantifies the amount of variation or dispersion of price data points "
        "from their moving average. High values indicate that prices are spread "
        "out over a wider range (high volatility), while low values indicate "
        "that price is consolidating closely around its average (low volatility)."
    )

def meta() -> Dict:
    """
    Metadata for the dual-engine orchestrator.
    """
    return {
        "author": "Google Gemini",
        "version": 1.1,
        "verified": 1,
        "polars": 1  # Flag to trigger high-speed Polars execution
    }

def warmup_count(options: Dict[str, Any]) -> int:
    """
    Calculates the required warmup rows for Standard Deviation.
    """
    try:
        period = int(options.get('period', 20))
    except (ValueError, TypeError):
        period = 20

    # Consistent with other rolling-window stabilization buffers
    return period * 3

def position_args(args: List[str]) -> Dict[str, Any]:
    """
    Maps positional URL arguments to dictionary keys.
    Example: stddev_20 -> {'period': '20'}
    """
    return {
        "period": args[0] if len(args) > 0 else "20"
    }

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> pl.Expr:
    """
    High-performance Polars-native calculation using Lazy expressions.
    """
    # Parse Parameters
    try:
        period = int(options.get('period', 20))
    except (ValueError, TypeError):
        period = 20

    # High-speed vectorized rolling standard deviation
    return pl.col("close").rolling_std(window_size=period).round(5).alias(indicator_str)

def calculate(df: Any, options: Dict[str, Any]) -> Any:
    """
    Legacy fallback for Pandas-only environments.
    """
    import pandas as pd
    
    # 1. Parse Parameters
    try:
        period = int(options.get('period', 20))
    except (ValueError, TypeError):
        period = 20

    # 2. Determine Price Precision
    try:
        sample_price = str(df['close'].iloc[0])
        precision = len(sample_price.split('.')[1])+1 if '.' in sample_price else 2
    except (IndexError, AttributeError):
        precision = 5

    # 3. Vectorized Calculation Logic
    std_dev = df['close'].rolling(window=period).std()

    # 4. Final Formatting and Rounding
    res = pd.DataFrame({
        'std_dev': std_dev.round(precision)
    }, index=df.index)
    
    return res.dropna(subset=['std_dev'])