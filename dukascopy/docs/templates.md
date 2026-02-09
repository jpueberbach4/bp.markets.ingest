# Common templates for indicators

## 8. 📋 Common Indicator Patterns

The system indicators are [examples](../util/plugins/indicators). Use them as a guideline.

### 1. Simple Rolling Calculation

Pure polars expression based template. Use it with `meta.polars:1`.

When?

- No dependency on other timeframes/symbols
- Extreme performance
- Single value output

```python
# SMA, EMA, STDDEV, etc.
# Pure polars expression based edi
def calculate_polars(indicator_str, options):
    period = int(options.get('period', 20))
    return [pl.col("close").rolling_mean(period).alias(indicator_str)]
```

(this is the fastest path)

### 2. Multi-Output Indicator

Pure polars expression based template. Use it with `meta.polars:1`.

When?

- No dependency on other timeframes/symbols
- Extreme performance
- MULTI-value output

```python
# Bollinger Bands, MACD, etc.
def calculate_polars(indicator_str, options) -> Union[List[pl.Expr], pl.Expr]:
    return [
        expr1.alias(f"{indicator_str}__upper"),
        expr2.alias(f"{indicator_str}__middle"),
        expr3.alias(f"{indicator_str}__lower")
    ]
```

(this is the fastest path)

### 3. Cross-Timeframe/Symbol Indicator

Pandas or Polars dataframe based template. Use it with `meta.polars:0` and/or `meta.polars_input:1`.

When?

- Initial version for a pure polars-expression version
- Dependency on other timeframes/symbols
- Want to work with the data itself, either Pandas or Polars dataframe
- Debugging of the actual dataframe contents

Pandas dataframe example (meta.polars_input:0):

```python
# Requires get_data with merge_asof
def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    higher_tf_data = get_data(...)
    merged = pd.merge_asof(df, higher_tf_data, ...)
    return merged[['higher_tf_value']]
```

Polars dataframe example (meta.polars_input:1):

```python
# Requires get_data with merge_asof
def calculate(ldf: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    higher_ldf_data = get_data(..., options={"return_polars": True})
    return (
        ldf.lazy()
        .join_asof(higher_ldf_data, on="time_ms", strategy="backward")
        .select(["column"])
        .collect()
    )
```

### 4. ML Feature Indicator

Pandas or Polars dataframe based template. Use it with `meta.polars:0` and/or `meta.polars_input:1`.

When?

- Dependency on other indicators/features
- Want to work with the data itself for ml model prediction
- Debugging of the actual dataframe contents

Pandas dataframe example (meta.polars_input:0):

```python
# Uses pre-trained models
def calculate(df: pd.DataFrame, options: Dict[str, Any]) -> pd.DataFrame:
    # Use the passed 'df' (Pandas DataFrame) for the internal API call
    features = get_data_auto(df, indicators=['feature1', 'feature2'])

    # Generate predictions
    predictions = model.predict(features)

    # Return a Pandas DataFrame with the 'signal' column
    return pd.DataFrame({'signal': predictions})
```

Polars dataframe example (meta.polars_input:1):

```python
# Uses pre-trained models
def calculate(ldf: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    # Use the passed 'ldf' (Polars DataFrame) for the internal API call
    features = get_data_auto(ldf, indicators=['feature1', 'feature2'], options={"return_polars": True})
    
    # Generate predictions
    predictions = model.predict(features)
    
    # Return a Polars DataFrame with the 'signal' column
    return pl.DataFrame({
        'signal': predictions
    })
```

### 5. Extensive example with thread-optimization

This example plots 3x different TF RSI on a single panel for the current symbol and avoids repainting by using the `is-open` indicator to filter out `live-candles`.

```python
import polars as pl
import pandas as pd
import numpy as np
from typing import List, Dict, Any

def description() -> str:
    return (
        "Triple RSI Panel: Displays Current, 4H, and 1D RSI in a single panel. "
        "Uses data-relative 'is_open' filtering to prevent repainting on the live-edge."
    )

def meta() -> Dict:
    return {
        "author": "Google Gemini",
        "version": 2.6, 
        "panel": 1,
        "verified": 1,
        "polars": 0,
        "polars_input": 1
    }

def warmup_count(options: Dict[str, Any]) -> int:
    rsi_period = int(options.get('rsi_period', 14))
    # 1D is 1440 mins. We need a massive 1H lead time for 1D RSI convergence.
    return (rsi_period * 3) * 24

def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "rsi_period": args[0] if len(args) > 0 else "14"
    }

def calculate(df: pl.DataFrame, options: Dict[str, Any]) -> pl.DataFrame:
    # Import here so these only load when the function actually runs
    from util.api import get_data
    from concurrent.futures import ThreadPoolExecutor
    import polars as pl

    # Toggle for performance profiling (leave False in production)
    profiling_enabled = False
    if profiling_enabled:
        import cProfile, pstats, io
        pr = cProfile.Profile()
        pr.enable()

    # Read RSI period from options, defaulting to 14 if not provided
    rsi_period = int(options.get("rsi_period", 14))

    # Build the column name used by the indicator API (e.g. "rsi_14")
    rsi_col = f"rsi_{rsi_period}"

    # Create a lightweight DataFrame with only timestamps
    # This becomes the "reference timeline" for all joins
    ldf = df.select([
        pl.col("time_ms").cast(pl.UInt64)
    ])

    # Extract static metadata (assumed constant across all rows)
    # DO NOT USE THE LDF!
    symbol = df["symbol"].item(0)
    tf = df["timeframe"].item(0)

    # Determine the time range we need indicator data for
    time_min = df["time_ms"].min()
    time_max = df["time_ms"].max()

    # Force API to return Polars DataFrames
    api_opts = {**options, "return_polars": True}

    # One full day of extra history to stabilize RSI calculations
    warmup_ms = 86400000

    def fetch_indicator_data(target_tf, alias):
        # Fetch RSI + is-open flags for a given timeframe
        data = get_data(
            symbol=symbol,
            timeframe=target_tf,
            after_ms=time_min - (warmup_ms * 2),
            until_ms=time_max + 1,
            indicators=[rsi_col, "is-open"],
            limit=1000000,
            options=api_opts
        )

        # Convert to lazy mode for efficient joins
        # Drop open candles so values only update on closed bars
        # Rename the RSI column so multiple timeframes can coexist
        return (
            data.lazy()
            .filter(pl.col("is-open") == 0)
            .select([
                pl.col("time_ms").cast(pl.UInt64),
                pl.col(rsi_col).alias(alias)
            ])
            .sort("time_ms")
        )

    # Fetch RSI data for three timeframes in parallel to save time
    with ThreadPoolExecutor(max_workers=3) as executor:
        f_current = executor.submit(fetch_indicator_data, tf, "rsi")
        f_4h = executor.submit(fetch_indicator_data, "4h", "rsi4h")
        f_1d = executor.submit(fetch_indicator_data, "1d", "rsi1d")

        # Wait for all fetches to finish
        lazy_current = f_current.result()
        lazy_4h = f_4h.result()
        lazy_1d = f_1d.result()

    # Join all RSI streams onto the base timeline
    # Backward as-of join means "use the last known closed value"
    result_ldf = (
        ldf.lazy()
        .join_asof(lazy_current, on="time_ms", strategy="backward")
        .join_asof(lazy_4h, on="time_ms", strategy="backward")
        .join_asof(lazy_1d, on="time_ms", strategy="backward")
        .select(["rsi", "rsi4h", "rsi1d"])
        .collect()
    )

    # Stop profiling and print results if enabled
    if profiling_enabled:
        pr.disable()
        s = io.StringIO()
        ps = pstats.Stats(pr, stream=s).sort_stats("cumulative")
        ps.print_stats(20)
        print(s.getvalue())

    # Return the final DataFrame with one RSI per timeframe
    return result_ldf

```

Note the profiling section. It is VERY good practice to profile your code in order to see where, often unnecessary performance-loss, could sit.