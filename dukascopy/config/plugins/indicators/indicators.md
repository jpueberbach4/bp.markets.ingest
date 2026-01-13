# Building Custom Technical Indicators: A Developer's Guide

Extending our technical analysis engine with custom indicators is straightforward. Each indicator exists as a standalone Python plugin. To build one, you need to implement a specific set of functions that the engine uses for metadata, parameter mapping, and high-performance calculations.

**Plugins should be stored in your `config.user/plugins/indicators` directory**

**When you add a plugin you will need to restart the service. I think when its loaded, you dont need to restart anymore.**

**When plugin names collide with system ones, the system ones will get preference. Use unique names.**

---

## 1. The Plugin Architecture

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