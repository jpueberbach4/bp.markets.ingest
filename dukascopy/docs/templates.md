# Common templates for indicators

## 8. 📋 Common Indicator Patterns

The system indicators are [examples](../util/plugins/indicators). Use them as a guideline.

**Important notice:** You should always aim for Polars expressions (1 & 2 below). At this moment, I cannot improve a situation with the GIL involving thread-locking. For (3 & 4 below) threads are used to execute indicators in parallel. When dataframes get large a significant amount of time is spent in thread.acquire and thread.lock, the GIL, to move data back and forth between thread and main-thread. The GIL is a common limitation of Python. From version 3.14 there is an option to run free-threaded, which may, at least partly, solve some of my issues. Until then, the general advice is to keep dataframe sizes limited when you are using (3 & 4 below).

While the performance is extremely good, like god-tier for Python, a theoretical fix of the GIL-issue would put this almost in axiomatic-territory.

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

**Note:** Four thing about the example below:

1. It queries the is-open status to detect the open-candles (you will need to have the BTC-USD symbol synced up)
2. It discards the RSI of the open-candles. It only considers closed candles
3. This avoids repainting
4. This indicator is now "live-capable"


```python
import polars as pl
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
    return 0

def position_args(args: List[str]) -> Dict[str, Any]:
    return {
        "period": args[0] if len(args) > 0 else "14",
        "period-4h": args[0] if len(args) > 0 else "14",
        "period-1d": args[0] if len(args) > 0 else "14",
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
    rsi_period = int(options.get("period", 14))
    rsi_period_4h = int(options.get("period-4h", 14))
    rsi_period_1d = int(options.get("period-1d", 14))

    # Build the column name used by the indicator API (e.g. "rsi_14")
    rsi_col = f"rsi_{rsi_period}"
    rsi_col_4h = f"rsi_{rsi_period_4h}"
    rsi_col_1d = f"rsi_{rsi_period_1d}"

    # Create a lightweight DataFrame with only timestamps
    # This becomes the "reference timeline" for all joins
    ldf = df.select([
        pl.col("time_ms").cast(pl.UInt64)
    ])

    # Extract static metadata (assumed constant across all rows)
    symbol = df["symbol"].item(0)
    tf = df["timeframe"].item(0)

    # Determine the time range we need indicator data for
    # Changed this from O(N) (min(),max()) to O(1) operation.
    # On big chunks we don't want O(N) operations, anywhere.
    # When developing indicators, always ask yourself the question:
    # Is this an O(N) operation? Can it be replaced with a O(log N) 
    # or O(1) operation? Especially for ML important!
    # Incoming df's to calculate are always guaranteed to be asc on 
    # time_ms. No scans needed.
    time_min = df["time_ms"][0]
    time_max = df["time_ms"][-1]

    # Force API to return Polars DataFrames
    api_opts = {**options, "return_polars": True}

    warmup_ms = 86400000 * 5 # cover weekends + safety value

    def fetch_indicator_data(target_tf, alias, rsi_ind):
        # Fetch RSI + is-open flags for a given timeframe
        data = get_data(
            symbol=symbol,
            timeframe=target_tf,
            after_ms=time_min - warmup_ms,
            until_ms=time_max + 1,
            indicators=[rsi_ind, "is-open"],
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
        f_current = executor.submit(fetch_indicator_data, tf, "rsi", rsi_col)
        f_4h = executor.submit(fetch_indicator_data, "4h", "rsi4h", rsi_col_4h)
        f_1d = executor.submit(fetch_indicator_data, "1d", "rsi1d", rsi_col_1d)

        # Wait for all fetches to finish
        lazy_current = f_current.result()
        lazy_4h = f_4h.result()
        lazy_1d = f_1d.result()

    # Make a flat timeline to join into
    timeline = df.select([pl.col("time_ms").cast(pl.UInt64)]).lazy()
    # Join all RSI streams onto the base timeline
    # Backward as-of join means "use the last known closed value"
    result_ldf = (
        timeline
        .join_asof(lazy_current, on="time_ms", strategy="backward")
        .join_asof(lazy_4h, on="time_ms", strategy="backward")
        .join_asof(lazy_1d, on="time_ms", strategy="backward")
        .select(["rsi", "rsi4h", "rsi1d"])
        .collect(streaming=True)
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

### 6. Custom color-coding of your indicators

It is now possible to override the `getSeriesColor` javascript method in the interface using a `custom.js` javascript file. This allows you to apply specific line-colors to your custom indicators. You use the name of the column as the palette's `index`.

**Note:** For this to work set `http.reload:1` in your `config.user.yaml` (changing line colors is typically a development-mode thing).

**Note:** When you have `vscode` you can just hover over a color to open-up a color-picker.

**Note:** This file is not created or overwritten by `./setup-dukascopy.sh`.

Create a new file `config.user/dukascopy/http-docs/scripts/custom.js`, paste the following contents to it:

```javascript
function getSeriesColor(col) {
    const palette = {
        'stoch_k': '#2962FF',           // Blue
        'stoch_d': '#FF6D00',           // Orange
        'signal': '#FF5252',            // Red
        'macd': '#2962FF',              // Blue
        'upper': '#787b86',             // Gray
        'lower': '#787b86',             // Gray
        'middle': '#FF9800',            // Amber
        'rsi': '#9c27b0',               // Purple
        'hist': '#26a69a',              // Teal
        'confidence': '#FFD600',        // Orange
        'threshold': '#00FF00',         // Lime
        'relative-height': '#1B6E1B',   // Deep Forest
        'rsi4h': '#00FF00',             // Lime
        'rsi1d': '#FF5252',             // Lime
    };
    console.log(col);
    const mainParts = col.split('__');
    const suffix = (mainParts.length > 1 ? mainParts[1] : col.split('_').shift()).toLowerCase();
    color = 0;
    if (palette[suffix]) { 
        color = palette[suffix];
    } else {
        let hash = 0;
        for (let i = 0; i < col.length; i++) {
            hash = col.charCodeAt(i) + ((hash << 5) - hash);
        }
        color = `hsl(${Math.abs(hash % 360)}, 80%, 50%)`;
    }
    return color;
}
```

When done changing colors, press `Update View` in the interface, the new colors should be applied immediately. Without a need to refresh the interface or remove/re-add the indicator. 

**Note:** In a later version it will be possible to specify colors in the `meta` section of the indicator.

