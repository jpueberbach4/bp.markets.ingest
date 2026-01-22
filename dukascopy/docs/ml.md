# 🎯 ML Sniper: AI-Powered Market Bottom Detector

The ML Sniper system is a quantitative infrastructure that uses **Random Forest Classification** to identify high-probability reversal points (bottoms) in financial markets. It is designed to be conservative, prioritizing **precision (accuracy)** over **recall (frequency)**.

---

## 🏗️ 1. System Architecture

The project is divided into three distinct phases: **Training**, **Evaluation/Optimization**, and **Inference**.

### File Map
| File | Role | Description |
| :--- | :--- | :--- |
| `mltrain.py` | **Trainer** | Fetches historical data, generates labels, and builds the `.pkl` model. |
| `mloptimizer.py` | **Optimizer** | Brute-forces confidence thresholds to find the "Sweet Spot" for accuracy. |
| `mleval.py` | **Auditor** | Generates detailed Confusion Matrices and Precision/Recall reports. |
| `mlind.py` | **Inference** | A high-performance plugin for trading/API signal generation. |
| `mlplot.py` | **Visualization** | Graphs feature importance and internal decision tree logic. |

---

## 🧠 2. Core Concepts & Internal Logic

### A. The 4-Feature Stack
To ensure the AI understands "market context," raw OHLCV data is converted into four normalized features:

1.  **Trend Deviation**: `(Close - SMA50) / Close`. Measures how overextended the price is from its 50-period average.
2.  **Normalized RSI**: `RSI / 100`. Standardizes momentum into a fixed 0.0 to 1.0 range.
3.  **Volatility Ratio**: `ATR / Close`. Normalizes price movement relative to current market volatility.
4.  **Body Strength**: `(Close - Open) / ATR`. Measures the "force" of the current candle.



### B. The Labeling Logic (The "Truth")
The model is trained to find significant structural lows. 
* **Target**: A Local Low defined by a window of `X` periods. 
* **Daily Context**: If window=24, the AI treats the setup as a "Monthly Cycle Bottom."
* **Requirement**: Price must bounce at least 0.5 * ATR within 12 bars to validate the recovery.

### C. The Random Forest Engine
The system utilizes 200 independent Decision Trees. Each tree "votes" on whether a setup is a bottom.
* **Confidence Score**: If 150 out of 200 trees vote "Yes," the signal has a confidence of **0.75**.
* **Voting Mechanism**: This ensemble approach prevents the system from being fooled by single-indicator anomalies.

---

## 🚀 3. Installation & Usage

### Prerequisites
* Python 3.8+
* Upgrade dependencies
`pip install --upgrade pip setuptools wheel`

* Install scikit-learn
`pip install scikit-learn==1.3.2`

* Install joblib/matplotlib
`pip install joblib matplotlib`

* Test the scikit-learn installation
`python3 -c "import sklearn; print('Scikit-learn version:', sklearn.__version__)"`

* Install the visualization plugins
`cp examples/ml-bottom-ind.py config.user/plugins/indicators/ml-bottom-example.py`
`cp examples/ml-top-ind.py config.user/plugins/indicators/ml-top-example.py`

### Workflow

Note: Currently configured for GBP-USD.

1.  **Train the Model**:
    ```bash
    python3 examples/ml-bottom-train.py
    python3 examples/ml-top-train.py
    ```
    *This creates `GBP-USD-(bottom|top)-engine.pkl`.*

2.  **Optimize Thresholds**:
    ```bash
    python3 example/ml-bottom-optimizer.py
    python3 example/ml-top-optimizer.py
    ```
    *Look for the threshold that provides >90% precision.*

3.  **Run LIndicator**:
    Load `ml-bottom-example` into your server or terminal. The internal logic uses:
    * **Confidence Threshold**: `0.55 - 0.70` (Adjustable)
    * **Safety Filter**: `RSI < 40` and `Body Strength > 0` (Only buys green candles. Its a demo.).

    Load `ml-top-example` into your server or terminal. The internal logic uses:
    * **Confidence Threshold**: `0.55 - 0.70` (Adjustable)
    * **Safety Filter**: `RSI > 60` and `Body Strength > 0` (Only sells red candles. Its a demo.).

---

## 🛡️ 4. Anti-Bias Safety Features

The system is built to prevent the two most common failures in Trading AI:

* **Lookahead Bias (`:skiplast`)**: The system is designed to run with `:skiplast` at the API level. It only predicts based on **Closed Bars**. It never "cheats" by looking at the current live price. Use `:skiplast` during market-opens. eg `http://localhost:8000/ohlcv/1.1/select/EUR-USD,1d[ml(EUR-USD-engine.pkl,0.55)]:skiplast/after/1149033600000/output/JSON?limit=10&subformat=3&order=desc`. Gets you the last closed candle and signals on index 0.
* **Signal Repainting**: By utilizing index `-2` (the last completed candle), once a signal is generated, it is permanent and never changes.
* **Warmup Protection**: The system requires a `warmup_count` of 50 bars to ensure Moving Averages and ATRs are mathematically valid before making a prediction.

---

## 📊 5. Feature Importance
Based on current training for major pairs (GBP-USD, EUR-USD), the AI prioritizes the features in this order:
1.  **RSI Normalized** (~40%): The primary engine for finding exhaustion.
2.  **Trend Deviation** (~26%): Ensures we are buying at a relative discount.
3.  **Body Strength** (~18%): The "Trigger" that confirms the buyers have returned.
4.  **Volatility Ratio** (~15%): The "Scale" that adjusts for market noise.

Outputs:

```sh
~/repos2/bp.markets.ingest/dukascopy$ python3 examples/ml-bottom-eval.py
========================================
     SNIPER MODEL EVALUATION REPORT
========================================

[CONFUSION MATRIX]
True Negatives (Correctly Ignored): 2778
False Positives (Fake Signals):     0
False Negatives (Missed Bottoms):   49
True Positives (Sniper Hits):       26

[SNIPER ACCURACY]
Precision: 100.00%
~/repos2/bp.markets.ingest/dukascopy$ python3 examples/ml-bottom-optimizer.py
Optimizing: ~repos2/bp.markets.ingest/dukascopy/EUR-USD-engine.pkl
Optimizing Thresholds for EUR-USD...

==================================================
THRESHOLD  | SIGNALS    | PRECISION  | WINNERS
==================================================
0.50       | 59         | 89.83%     | 53
0.60       | 43         | 100.00%    | 43
0.65       | 26         | 100.00%    | 26
0.70       | 12         | 100.00%    | 12
0.75       | 5          | 100.00%    | 5
0.80       | 1          | 100.00%    | 1
0.85       | 0          | 0.00%      | 0
```

![ml-screenshot](../images/ml_example.png)

Run on EUR-USD 1d to see it in action. Fork and experiment — it's a learning tool!

Test on your localhost, select EUR-USD 1d graph, select the ml-example indicator, default settings if EUR-USD. Browse. See recent years history-it was trained on recent years. Its not perfect, but as a demo. Pretty neat.

![ml-screenshot](../images/ml_example2.png)

![ml-screenshot](../images/ml_example3.png)

This is an exact showcase on how i use this system. The API calls are pulled by EA's. You can change the scripts to train for other assets as well. This works for more Forex pairs. 


**Note:** This favors high accuracy, leading to few trading signals each year for daily per asset. But ofcourse, you dont run this on a single asset but on 40-80 simultaneously..... the above examples can be tuned and become a very usable base.

---
*Developed as a high-precision, low-frequency sniper system for quantitative trading. Most accurate on high timeframes*