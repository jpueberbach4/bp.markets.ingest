# Building Custom Technical Indicators: A Developer's Guide

Extending our technical analysis engine with custom indicators is straightforward. Each indicator exists as a standalone Python plugin. To build one, you need to implement a specific set of functions that the engine uses for metadata, parameter mapping, and high-performance calculations.

**Plugins should be stored in your `config.user/plugins/indicators` directory**

**When plugin names collide with system ones, the system ones will get preference. Use unique names.**

**Do not use '_' in indicator filenames. Use a '-' (dash) or a '.' (dot) if you need to seperate**

---

## 1. The Plugin Architecture

**Note:** The plugin engine now supports hybrid-execution of both pandas-based and polars-based indicators. General advice is when you build indicators that do not rely on UDF (User-Defined-Functions), use the Polars way (use Gemini to support you) for the highest possible performance. IF heavily dependent on UDF or for quick-iteration: use the pandas way. NON-UDF versions: generally you would want to implement them both and test which one gives the best performance. Eg use a million+ rows for performance tests.

Every plugin must be a valid Python file (e.g., `my_indicator.py`) containing the following core functions:

### `description() -> str`
This returns a human-readable string. It is used by the UI and API documentation to explain what the indicator does and how to interpret its signals.
> **Tip:** Keep it concise but mention the core mathematical logic (e.g., "Uses a 14-period EMA").

### `meta() -> Dict`
Returns a dictionary of metadata. At a minimum, include `author` and `version`. This is useful for tracking updates and credits in the indicator library.

### `warmup_count(options: Dict) -> int`
This function tells the engine how many historical bars are needed before the indicator becomes "valid." 
* **SMA:** Needs at least `period` bars.
* **Recursive (EMA/RSI):** Usually needs `period * 3` bars to allow the smoothing algorithm to converge.

### `position_args(args: List[str]) -> Dict`
This maps URL-style positional arguments into a clean dictionary. 
* *Input:* `['14', '2.0']` (from a request like `/api/bbands_14_2.0`)
* *Output:* `{'period': 14, 'std': 2.0}`

### `calculate(df: pd.DataFrame, options: Dict) -> pd.DataFrame`
The heart of the plugin. It receives a Pandas DataFrame with OHLCV data and must return a DataFrame of the same length containing the calculated values.

make sure to set `polars:0` in the meta section OR leave it out.

**OR/AND**

### `calculate_polars(indicator_str: str, options: Dict[str, Any]) -> pl.Expr|List[pl.expr]`
The high-performance heart of the plugin for the Polars engine. Unlike the Pandas version, this does not receive a DataFrame; instead, it returns one or more Polars Expressions (pl.Expr) that are injected into the engine's lazy execution graph. This allows the IndicatorEngine to optimize the entire calculation across all requested indicators in a single pass.

make sure to set `polars:1` in the meta section.

---

## 2. Implementation Template

Using the **Bollinger Bands** plugin as a reference, here is the standard structure:

```python
import pandas as pd
import numpy as np
from typing import List, Dict, Any

def description() -> str:
    return "Bollinger Bands measure volatility using a central SMA and SD bands."

def meta() -> Dict:
    return {"author": "DevTeam", "version": 1.1}

def warmup_count(options: Dict) -> int:
    period = int(options.get('period', 20))
    return period * 3

def position_args(args: List[str]) -> Dict:
    return {
        "period": args[0] if len(args) > 0 else "20",
        "std": args[1] if len(args) > 1 else "2.0"
    }

def calculate(df: pd.DataFrame, options: Dict) -> pd.DataFrame:
    period = int(options.get('period', 20))
    std_mult = float(options.get('std', 2.0))
    
    # Use Vectorized Operations for speed
    mid = df['close'].rolling(window=period).mean()
    std = df['close'].rolling(window=period).std()
    
    return pd.DataFrame({
        'upper': mid + (std * std_mult),
        'mid': mid,
        'lower': mid - (std * std_mult)
    }, index=df.index)

def calculate_polars(indicator_str: str, options: Dict[str, Any]) -> List[pl.Expr]:
    """This is for speed. Lazy execution"""
    try:
        period = int(options.get('period', 20))
        std_dev = float(options.get('std', 2.0))
    except (ValueError, TypeError):
        period, std_dev = 20, 2.0

    mid = pl.col("close").rolling_mean(window_size=period)
    std = pl.col("close").rolling_std(window_size=period)

    upper = mid + (std * std_dev)
    lower = mid - (std * std_dev)

    return [
        upper.alias(f"{indicator_str}__upper"),
        mid.alias(f"{indicator_str}__mid"),
        lower.alias(f"{indicator_str}__lower")
    ]

```

**Note:** When you are building an oscillator or panel-indicator, specify `panel:1` in the meta section.

```python
def meta() -> Dict:
    return {"author": "DevTeam", "version": 1.1, "panel": 1}
```

**Note:** When you are building a complete chart-overlay, specify `chart:1` in the meta section. Note that this is currently unsupported but this is coming (example eg is a renko chart).

```python
def meta() -> Dict:
    return {"author": "DevTeam", "version": 1.1, "chart": 1}
```


## 3. Pro-Tip: Accelerate Development with Gemini

The most efficient way to build new plugins is to leverage Google Gemini as a pair programmer. Because the engine follows a strict functional contract, you can "train" the AI on the structure once and generate dozens of indicators.

The "Pre-build" Workflow:

* Upload a Reference: Upload an existing, working script (like bbands.py or sma.py) to the chat.

* Define the Pattern: Tell Gemini: "Use this file as a template for the function signatures and coding style."

* Request New Indicators: Simply say: "Give me the indicator script for [Indicator Name]" (e.g., "Give me the indicator script for Keltner Channels").

Gemini will automatically generate the warmup_count, the vectorized calculate logic, and the position_args mapping based on the standard library pattern.

## 4. Best Practices

Vectorization: Always use pandas or numpy vectorized functions. Avoid for loops inside calculate unless the indicator is highly path-dependent (like Renko).

Precision: Use the first row of data to determine the asset's precision and round your outputs accordingly to keep the API responses clean.

Stability: If your indicator uses division, always use .replace(0, np.nan) on the denominator to avoid Inf errors.

Performance: NON-UDF implementations should be in Polars expressions. Polars may be slower when using UDF.

Generic: implement both the `calculate` and `calculate_polars` methods. Implement in pandas, convert to polars using Gemini.

For inter-data/indicator querying within indicators, consult [this documentation](interdata.md).

## 5. Debugging

You can just print(df) from your Pandas based indicator and have that print showup in your console where you started the webservice with `./service.sh start`-if testing via the web-interface. If using the direct get_data approach, then i probably don't need to say anything else. You know.

For profiling, performance bottleneck finding in your indicators, use cProfile. At the start of your indicator enable the cProfile profiler and just before the end of the function, disable the profiler and print its stats. 

eg

```python

def calculate(df: pd.DataFrame, options: Dict) -> pd.DataFrame:
    import cProfile
    import pstats
    import io
    pr = cProfile.Profile()
    pr.enable()

    ## YOUR HEAVY CODE GOES HERE ##

    pr.disable()
    s = io.StringIO()
    sortby = 'cumulative'   # Can also use 'tottime' to see self-time
    ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
    ps.print_stats(30)      # Show top 30 most time-consuming calls
    print(s.getvalue())     # See console

    return df
```

Its generally good practice to profile your code after your first working implementation. Especially if you use your custom indicator for later feature-extraction for ML.

## 6. One more thing, your custom indicators in an external path?

Solve this by creating a config.users/plugins directory and then "symbolic link" your indicators path in there. 

eg

```sh
mkdir -p config.user/plugins
# delete the existing default one, be careful if you have something in there
rm -rf config.user/plugins/indicators
# now link your external path
ln -s /path/to/my/private/repo/indicators config.user/plugins/indicators
# your custom indicators are now linked to an path outside of the project
# config.user is excluded in .gitignore so you can put in there what you want.
ls -l config.users/plugins/indicators
# It should show an arrow pointing to your private repo: indicators -> /path/to/my/private/repo/indicators
```

This solves any version control issues or at least make it easier.

One last piece of advice. When using this for feature engineering. Use custom indicators to build your features. You can then just use the get_data internal API to get the dataframe with your computed indicators and push that directly, together with all the other indicators, into a model. This is a better way-performance-wise-than building a custom set of "feature classes". 

I am currently converting my feature-classes to indicators-polars where possible.

eg Write features once → Use everywhere (API, web, ML, backtesting)

Last example: i have features A,B,C implemented as indicators(features). I trained my model by querying get_data with indicators A,B,C(features). Now, i have an indicator which uses the model and needs A,B,C features. I do in that indicator a get_data_auto(df,[A,B,C]) and then call the model with that dataframe and get it's confidence and signals. This is high performant and works. I tested. Be careful for recursive patterns though. Unlimited loops. There is currently no protection for this, but also that is coming in future versions. This way you eliminate any feature-replication between training and inference.