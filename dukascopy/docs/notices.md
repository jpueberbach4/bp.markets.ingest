# ML

Ok. I have been playing with this all weekend. Here is the heads-up

- Is it useful? `Yes`
- What timeframe works this best on? `1d forex (only tested it there atm)` 
- What is the maximum accuracy you achieved? `86% (where the missing 14% are misses)` 
- Is that in-sample, OOS-train, or truly OOS? `All 3 combined in a single scan (2025-NOW)`
- Are you happy? `VERY! Worth the effort.`
- Is there diagnostic tooling? Yes, there is. `./run-mldiag.sh`
- is it CPU capable? `Yes, its capable but NO, you should have a Cuda capable GPU`
- Did you try tops-hunting, instead of only bottoms? `Not yet, but the plan is to have a 1d bottomdetect, have it enter positions and step out at tops (automated).`
- Are you going to use this yourself? `More tests needed, but very likely (money is involved so need to be 1000% sure)`
- So what's the plan now you achieved 86 percent accuracy? `Broader tests on more assets. Seeing if the approach works for commodities/stocks/indices (today tests)`. See [more assets](../images/ml-example/) to follow.
- Are you going to write up all of this? `Yes. Thats something for early next week. There is a LOT to tell on neuro-evolution.`
- What diagnostics are available? `Inspection of the model, threshold scan and walkforward tests. More will get added`
- Performance? `poor (in my world). the inference is just not as fast as i would like it to be. tried memory residency but still poor. researching. it currently feels like i am dragging an anchor.`
- Any short term related stuff? `Yes. Some of the example indicators will be made more robust and get integrated as system indicators. I will also share the "no-peek-ahead" fixes which i have locally.`
- Andromeda? `shifted to next week. Also different approach. I will abstract the "get_data" in the core code instead. You will be able to feed get_data options to select what kind of API it should use (HTTP, Bootstrap or files)`

Example diagnostics command and output:

```sh
./run-mldiag.sh --mode full --model checkpoints/model-best-gen12-f1-0.7692.pt \
--symbol GBP-USD --timeframe 1d --center example-pivot-finder_10_bottoms --threshold 0.23

🧬 [Model Inspector]: Initiating Deep Scan of 'model-best-gen12-f1-0.7692.pt'
======================================================================
📦 [Architecture]: Input Dim: 128 | Hidden Dim: 8 | Out Dim: 1
🎯 [Threshold]:   0.332000
🧬 [Gene Count]:   8
----------------------------------------------------------------------
🔬 [Normalization Diagnostics]: Checking for Z-Mean/Std anomalies...
   ✅ All normalization vectors look healthy.
----------------------------------------------------------------------
📊 [Gene Importance Analysis]: Ranking structural impact...
    1. example-multi-tf-rsi_DOLLAR.IDX-USD_14_14_14_14__rsi1W | Impact:  1.16%
    2. ppo_12_26_9__signal                                | Impact:  1.06%
    3. cci_20                                             | Impact:  1.06%
    4. williamsr_14                                       | Impact:  0.98%
    5. example-multi-tf-rsi_EUR-USD_14_14_14_14__rsi      | Impact:  0.71%
    6. example-multi-tf-rsi_DOLLAR.IDX-USD_14_14_14_14__rsi1d | Impact:  0.67%
    7. example-multi-tf-rsi_EUR-USD_14_14_14_14__rsi1W    | Impact:  0.57%
    8. example-multi-tf-rsi_GBP-USD_14_14_14_14__rsi1W    | Impact:  0.57%
======================================================================
✅ [Model Inspector]: Deep Scan Complete.


🎯 [Threshold Scanner]: Mapping probability distributions for 'model-best-gen12-f1-0.7692.pt'...
📊 [Data Imprint]: 301 bars analyzed | 9 total targets found.
--------------------------------------------------------------------------------
Threshold    | F1 Score   | Precision  | Recall     | Hits (TP)  | Noise (FP)
--------------------------------------------------------------------------------
0.100        | 0.3784     | 0.2500     | 0.7778     | 7          | 21
0.300        | 0.6250     | 0.7143     | 0.5556     | 5          | 2
0.500        | 0.5000     | 1.0000     | 0.3333     | 3          | 0
0.700        | 0.2000     | 1.0000     | 0.1111     | 1          | 0
0.900        | 0.0000     | 0.0000     | 0.0000     | 0          | 0
--------------------------------------------------------------------------------
🏆 [Optimal F1 Factory Spec]:
   -> Threshold: 0.3590
   -> F1 Score:  0.7143

🎯 [SNIPER GROUND TRUTH] (Highest Precision / Minimum Noise):
   -> Threshold:   0.3590
   -> Precision:   100.00%
   -> Targets Hit: 5 / 9
   -> False Alarms: 0
================================================================================
🔍 [Forensic Stepper]: Mapping target coordinates for 'example-pivot-finder_10_bottoms'...
🎯 [Forensic Stepper]: Extracted 9 confirmed targets.

🚀 [Forensic Stepper]: Initiating Walk-Forward Execution.
📦 Active Model: model-best-gen12-f1-0.7692.pt | Threshold: 0.2300
---------------------------------------------------------------------------------------------------------
Step    1/301 | Time: 2025-01-02 00:00:00 | Bars:    1 | Close:   1.23768 (+0.0000% ) | Score: 0.016643 |
Step    2/301 | Time: 2025-01-03 00:00:00 | Bars:    2 | Close:   1.24168 (+0.3232% ) | Score: 0.019414 |
Step    3/301 | Time: 2025-01-06 00:00:00 | Bars:    3 | Close:   1.25168 (+0.8054% ) | Score: 0.001606 |
Step    4/301 | Time: 2025-01-07 00:00:00 | Bars:    4 | Close:   1.24755 (-0.3300% ) | Score: 0.001103 |
Step    5/301 | Time: 2025-01-08 00:00:00 | Bars:    5 | Close:   1.23604 (-0.9226% ) | Score: 0.007771 |
Step    6/301 | Time: 2025-01-09 00:00:00 | Bars:    6 | Close:   1.23040 (-0.4563% ) | Score: 0.029474 |
Step    7/301 | Time: 2025-01-10 00:00:00 | Bars:    7 | Close:   1.22044 (-0.8095% ) | Score: 0.042716 |
Step    8/301 | Time: 2025-01-13 00:00:00 | Bars:    8 | Close:   1.21994 (-0.0410% ) | Score: 0.239437 | 🟢 FIRE   🎯 HIT
Step    9/301 | Time: 2025-01-14 00:00:00 | Bars:    9 | Close:   1.22115 (+0.0992% ) | Score: 0.058882 |
Step   10/301 | Time: 2025-01-15 00:00:00 | Bars:   10 | Close:   1.22374 (+0.2121% ) | Score: 0.028319 |
Step   11/301 | Time: 2025-01-16 00:00:00 | Bars:   11 | Close:   1.22384 (+0.0082% ) | Score: 0.014251 |
Step   12/301 | Time: 2025-01-17 00:00:00 | Bars:   12 | Close:   1.21583 (-0.6545% ) | Score: 0.039630 | STOPLOSS
Step   13/301 | Time: 2025-01-20 00:00:00 | Bars:   13 | Close:   1.23247 (+1.3686% ) | Score: 0.004158 |
Step   14/301 | Time: 2025-01-21 00:00:00 | Bars:   14 | Close:   1.23550 (+0.2458% ) | Score: 0.004859 |
Step   15/301 | Time: 2025-01-22 00:00:00 | Bars:   15 | Close:   1.23120 (-0.3480% ) | Score: 0.002222 |
Step   16/301 | Time: 2025-01-23 00:00:00 | Bars:   16 | Close:   1.23506 (+0.3135% ) | Score: 0.003134 |
Step   17/301 | Time: 2025-01-24 00:00:00 | Bars:   17 | Close:   1.24757 (+1.0129% ) | Score: 0.015809 |
Step   18/301 | Time: 2025-01-27 00:00:00 | Bars:   18 | Close:   1.24960 (+0.1627% ) | Score: 0.008447 |
Step   19/301 | Time: 2025-01-28 00:00:00 | Bars:   19 | Close:   1.24388 (-0.4577% ) | Score: 0.001173 |
Step   20/301 | Time: 2025-01-29 00:00:00 | Bars:   20 | Close:   1.24469 (+0.0651% ) | Score: 0.001380 |
Step   21/301 | Time: 2025-01-30 00:00:00 | Bars:   21 | Close:   1.24124 (-0.2772% ) | Score: 0.000267 |
Step   22/301 | Time: 2025-01-31 00:00:00 | Bars:   22 | Close:   1.23919 (-0.1652% ) | Score: 0.000147 |
Step   23/301 | Time: 2025-02-03 00:00:00 | Bars:   23 | Close:   1.24483 (+0.4551% ) | Score: 0.000085 |
Step   24/301 | Time: 2025-02-04 00:00:00 | Bars:   24 | Close:   1.24764 (+0.2257% ) | Score: 0.000113 |
Step   25/301 | Time: 2025-02-05 00:00:00 | Bars:   25 | Close:   1.25038 (+0.2196% ) | Score: 0.000102 |
Step   26/301 | Time: 2025-02-06 00:00:00 | Bars:   26 | Close:   1.24307 (-0.5846% ) | Score: 0.000132 |
Step   27/301 | Time: 2025-02-07 00:00:00 | Bars:   27 | Close:   1.23965 (-0.2751% ) | Score: 0.000010 |
Step   28/301 | Time: 2025-02-10 00:00:00 | Bars:   28 | Close:   1.23657 (-0.2485% ) | Score: 0.000045 |
Step   29/301 | Time: 2025-02-11 00:00:00 | Bars:   29 | Close:   1.24438 (+0.6316% ) | Score: 0.000388 |
Step   30/301 | Time: 2025-02-12 00:00:00 | Bars:   30 | Close:   1.24436 (-0.0016% ) | Score: 0.000909 |
Step   31/301 | Time: 2025-02-13 00:00:00 | Bars:   31 | Close:   1.25645 (+0.9716% ) | Score: 0.000035 |
Step   32/301 | Time: 2025-02-14 00:00:00 | Bars:   32 | Close:   1.25832 (+0.1488% ) | Score: 0.000000 |
Step   33/301 | Time: 2025-02-17 00:00:00 | Bars:   33 | Close:   1.26233 (+0.3187% ) | Score: 0.000000 |
Step   34/301 | Time: 2025-02-18 00:00:00 | Bars:   34 | Close:   1.26115 (-0.0935% ) | Score: 0.000003 |
Step   35/301 | Time: 2025-02-19 00:00:00 | Bars:   35 | Close:   1.25846 (-0.2133% ) | Score: 0.000051 |
Step   36/301 | Time: 2025-02-20 00:00:00 | Bars:   36 | Close:   1.26671 (+0.6556% ) | Score: 0.000023 |
Step   37/301 | Time: 2025-02-21 00:00:00 | Bars:   37 | Close:   1.26274 (-0.3134% ) | Score: 0.000161 |
Step   38/301 | Time: 2025-02-24 00:00:00 | Bars:   38 | Close:   1.26237 (-0.0293% ) | Score: 0.001487 |
Step   39/301 | Time: 2025-02-25 00:00:00 | Bars:   39 | Close:   1.26645 (+0.3232% ) | Score: 0.006177 |
Step   40/301 | Time: 2025-02-26 00:00:00 | Bars:   40 | Close:   1.26740 (+0.0750% ) | Score: 0.002916 |
Step   41/301 | Time: 2025-02-27 00:00:00 | Bars:   41 | Close:   1.25985 (-0.5957% ) | Score: 0.000380 |
Step   42/301 | Time: 2025-02-28 00:00:00 | Bars:   42 | Close:   1.25744 (-0.1913% ) | Score: 0.000412 |
Step   43/301 | Time: 2025-03-03 00:00:00 | Bars:   43 | Close:   1.26993 (+0.9933% ) | Score: 0.000004 |
Step   44/301 | Time: 2025-03-04 00:00:00 | Bars:   44 | Close:   1.27927 (+0.7355% ) | Score: 0.000000 |
Step   45/301 | Time: 2025-03-05 00:00:00 | Bars:   45 | Close:   1.28916 (+0.7731% ) | Score: 0.000000 |
Step   46/301 | Time: 2025-03-06 00:00:00 | Bars:   46 | Close:   1.28783 (-0.1032% ) | Score: 0.000000 |
Step   47/301 | Time: 2025-03-07 00:00:00 | Bars:   47 | Close:   1.29167 (+0.2982% ) | Score: 0.000000 |
Step   48/301 | Time: 2025-03-10 00:00:00 | Bars:   48 | Close:   1.28743 (-0.3283% ) | Score: 0.000000 |
Step   49/301 | Time: 2025-03-11 00:00:00 | Bars:   49 | Close:   1.29497 (+0.5857% ) | Score: 0.000000 |
Step   50/301 | Time: 2025-03-12 00:00:00 | Bars:   50 | Close:   1.29619 (+0.0942% ) | Score: 0.000000 |
Step   51/301 | Time: 2025-03-13 00:00:00 | Bars:   51 | Close:   1.29505 (-0.0880% ) | Score: 0.000000 |
Step   52/301 | Time: 2025-03-14 00:00:00 | Bars:   52 | Close:   1.29274 (-0.1784% ) | Score: 0.000001 |
Step   53/301 | Time: 2025-03-17 00:00:00 | Bars:   53 | Close:   1.29906 (+0.4889% ) | Score: 0.000000 |
Step   54/301 | Time: 2025-03-18 00:00:00 | Bars:   54 | Close:   1.30000 (+0.0724% ) | Score: 0.000000 |
Step   55/301 | Time: 2025-03-19 00:00:00 | Bars:   55 | Close:   1.30019 (+0.0146% ) | Score: 0.000003 |
Step   56/301 | Time: 2025-03-20 00:00:00 | Bars:   56 | Close:   1.29650 (-0.2838% ) | Score: 0.000103 |
Step   57/301 | Time: 2025-03-21 00:00:00 | Bars:   57 | Close:   1.29117 (-0.4111% ) | Score: 0.009411 |
Step   58/301 | Time: 2025-03-24 00:00:00 | Bars:   58 | Close:   1.29210 (+0.0720% ) | Score: 0.012100 |
Step   59/301 | Time: 2025-03-25 00:00:00 | Bars:   59 | Close:   1.29430 (+0.1703% ) | Score: 0.014614 |
Step   60/301 | Time: 2025-03-26 00:00:00 | Bars:   60 | Close:   1.28849 (-0.4489% ) | Score: 0.004173 |
Step   61/301 | Time: 2025-03-27 00:00:00 | Bars:   61 | Close:   1.29477 (+0.4874% ) | Score: 0.015985 |
Step   62/301 | Time: 2025-03-28 00:00:00 | Bars:   62 | Close:   1.29378 (-0.0765% ) | Score: 0.009258 |
Step   63/301 | Time: 2025-03-31 00:00:00 | Bars:   63 | Close:   1.29170 (-0.1608% ) | Score: 0.001568 |
Step   64/301 | Time: 2025-04-01 00:00:00 | Bars:   64 | Close:   1.29213 (+0.0333% ) | Score: 0.046210 |
Step   65/301 | Time: 2025-04-02 00:00:00 | Bars:   65 | Close:   1.30055 (+0.6516% ) | Score: 0.000000 |
Step   66/301 | Time: 2025-04-03 00:00:00 | Bars:   66 | Close:   1.30990 (+0.7189% ) | Score: 0.000000 |
Step   67/301 | Time: 2025-04-04 00:00:00 | Bars:   67 | Close:   1.28915 (-1.5841% ) | Score: 0.000011 |
Step   68/301 | Time: 2025-04-07 00:00:00 | Bars:   68 | Close:   1.27196 (-1.3334% ) | Score: 0.540442 | 🟢 FIRE   🎯 HIT
Step   69/301 | Time: 2025-04-08 00:00:00 | Bars:   69 | Close:   1.27638 (+0.3475% ) | Score: 0.331960 | 🟢 FIRE
Step   70/301 | Time: 2025-04-09 00:00:00 | Bars:   70 | Close:   1.28181 (+0.4254% ) | Score: 0.005104 |
Step   71/301 | Time: 2025-04-10 00:00:00 | Bars:   71 | Close:   1.29634 (+1.1336% ) | Score: 0.000001 |
Step   72/301 | Time: 2025-04-11 00:00:00 | Bars:   72 | Close:   1.30850 (+0.9380% ) | Score: 0.000000 |
Step   73/301 | Time: 2025-04-14 00:00:00 | Bars:   73 | Close:   1.31881 (+0.7879% ) | Score: 0.000000 |
Step   74/301 | Time: 2025-04-15 00:00:00 | Bars:   74 | Close:   1.32274 (+0.2980% ) | Score: 0.000000 |
Step   75/301 | Time: 2025-04-16 00:00:00 | Bars:   75 | Close:   1.32399 (+0.0945% ) | Score: 0.000000 |
Step   76/301 | Time: 2025-04-17 00:00:00 | Bars:   76 | Close:   1.32643 (+0.1843% ) | Score: 0.000000 |
Step   77/301 | Time: 2025-04-18 00:00:00 | Bars:   77 | Close:   1.32892 (+0.1877% ) | Score: 0.000000 |
Step   78/301 | Time: 2025-04-21 00:00:00 | Bars:   78 | Close:   1.33759 (+0.6524% ) | Score: 0.000000 | TAKEPROFIT
Step   79/301 | Time: 2025-04-22 00:00:00 | Bars:   79 | Close:   1.33297 (-0.3454% ) | Score: 0.000000 |
Step   80/301 | Time: 2025-04-23 00:00:00 | Bars:   80 | Close:   1.32494 (-0.6024% ) | Score: 0.000000 |
Step   81/301 | Time: 2025-04-24 00:00:00 | Bars:   81 | Close:   1.33386 (+0.6732% ) | Score: 0.000000 |
Step   82/301 | Time: 2025-04-25 00:00:00 | Bars:   82 | Close:   1.33065 (-0.2407% ) | Score: 0.000000 |
Step   83/301 | Time: 2025-04-28 00:00:00 | Bars:   83 | Close:   1.34394 (+0.9988% ) | Score: 0.000000 |
Step   84/301 | Time: 2025-04-29 00:00:00 | Bars:   84 | Close:   1.34046 (-0.2589% ) | Score: 0.000000 |
Step   85/301 | Time: 2025-04-30 00:00:00 | Bars:   85 | Close:   1.33254 (-0.5908% ) | Score: 0.000002 |
Step   86/301 | Time: 2025-05-01 00:00:00 | Bars:   86 | Close:   1.32766 (-0.3662% ) | Score: 0.000013 |
Step   87/301 | Time: 2025-05-02 00:00:00 | Bars:   87 | Close:   1.32596 (-0.1280% ) | Score: 0.000021 |
Step   88/301 | Time: 2025-05-05 00:00:00 | Bars:   88 | Close:   1.32942 (+0.2609% ) | Score: 0.000111 |
Step   89/301 | Time: 2025-05-06 00:00:00 | Bars:   89 | Close:   1.33644 (+0.5280% ) | Score: 0.000022 |
Step   90/301 | Time: 2025-05-07 00:00:00 | Bars:   90 | Close:   1.32909 (-0.5500% ) | Score: 0.000123 |
Step   91/301 | Time: 2025-05-08 00:00:00 | Bars:   91 | Close:   1.32441 (-0.3521% ) | Score: 0.016428 |
Step   92/301 | Time: 2025-05-09 00:00:00 | Bars:   92 | Close:   1.32964 (+0.3949% ) | Score: 0.028001 |
Step   93/301 | Time: 2025-05-12 00:00:00 | Bars:   93 | Close:   1.31744 (-0.9175% ) | Score: 0.752603 | 🟢 FIRE   🎯 HIT
Step   94/301 | Time: 2025-05-13 00:00:00 | Bars:   94 | Close:   1.33035 (+0.9799% ) | Score: 0.271783 | 🟢 FIRE
Step   95/301 | Time: 2025-05-14 00:00:00 | Bars:   95 | Close:   1.32613 (-0.3172% ) | Score: 0.171849 |
Step   96/301 | Time: 2025-05-15 00:00:00 | Bars:   96 | Close:   1.33007 (+0.2971% ) | Score: 0.059124 | ...
...
```

>Note: the second fire is interesting. It basically catches a falling-knife. Don't know if i will have the "balls" to enter positions on these kind of candles. We'll see in paper trading.

This is not the end of the ML-experience. I will be doubling down on lower timeframes but 1d is the first target to get stable and it is already nearly at that. Documentation will come. In a somewhat similar style as `configuration.md`. From introduction, to concepts, to caveats, to guided most-complex asset configuration.

You need to know some stuff about tuning model parameters in the universes. How to penalize for non-precision, how to build a carpet bomber, what features to select, the generic thinking way behind all of this stuff. A seperate document will be created on how to extend the code.

Give me a few days to write the stuff up. Will be like 4-5 A4 pages of information.

Very promising. The primary idea behind all of this project seems feasible.

>Note to self: If you are 1000% sure the model architecture is stable, export the .pt to ONNX and then to TensorRT. 5-20x speedup on inference.

PS: i know this is complex/very advanced stuff for a "typical trader with some python experience". It was for me too. Like one and a half week ago i also was in the "how the hell should i approach this. i have zero experience"-mode... in the end it turned out pretty well. The concepts look difficult at first but eventually the `aha` moment comes and then you think `wait. i am starting to grasp the stuff and it clicks all in place`. wait for the documentation, will be fine if you cannot grasp it just yet.

# 🚀 Release Update: Developer UX & Surgical Maintenance

This project is a high-performance market research and analysis tool focused on feature engineering. While optimized for **"mechanical sympathy"** at the hardware level, these latest additions focus on improving the daily workflow for developers and researchers.

---

## 🖥️ Interface & DX Improvements

We have applied several targeted improvements to the web interface to streamline the developer experience (DX) and speed up cross-asset configuration:

* **Indicator Tooltips:** You can now hover over any indicator in the selection box to see its specific description and parameter requirements.
* **`Copy API` Button:** A new utility to instantly translate your current chart state (Symbol, Timeframe, visible window, and active indicators) into a ready-to-use internal Python API call.
* **Quick Symbol Copy:** Clicking the "Symbol" label directly above the selector now copies the symbol name to your clipboard. This is designed to speed up correlation studies or the configuration of benchmark indicators (e.g., Pearson correlation).

> [!IMPORTANT]
> To enable these features, you must copy the latest files from `config/dukascopy/http-docs` to your `config.user/dukascopy/http-docs` directory.

### Example `Copy API` Output
The following string is generated based on your current viewport and indicator stack:

```python
get_data('AAPL.US-USD', '1h', after_ms=1767362400000, limit=1000, order="asc",
  indicators=["aroon_14","bbands_20_2.0","feature-mad_20_close_sma",
              "feature-nprice_14_close_log","feature-natr_14_0","feature-vzscore_20_log"], 
  options={**options, "return_polars": True})
```

## 🛠️ Surgical Maintenance Tools

The rebuild logic has been optimized to support targeted operations. This allows you to repair or update specific instruments without performing a "scorched-earth" rebuild of the entire data warehouse.

### 1. Targeted Full Rebuilds
You can now rebuild specific symbols and their associated aliases (Sidetracked/Adjusted sets) across all layers (**transform**, **aggregate**, **resample**):

**Bash**
```bash
./rebuild-full.sh --symbol BRENT.CMD-USD --symbol AAPL.US-USD
```

You can also use this when you have just added a new symbol `./rebuild-full.sh --symbol NEWSYMBOL`.

### 2. Targeted Weekly "Safety-Net"
For instruments dealing with illiquid data or those requiring regular backfill maintenance (where brokers often retroactively change the last few days of data), `rebuild-weekly.sh` now supports the same targeted syntax:

**Bash**
```bash
./rebuild-weekly.sh --symbol ETH-USD
```

### ⚠️ Important Notes

* **Back-Adjusted Sets:** When rebuilding adjusted sets (e.g., `BRENT.CMD-USD-PANAMA`), ensure you specify the origin (source) symbol.
* **Naming:** Always ensure adjusted sets are prefixed with the original symbol (e.g., `SYMBOL-RR`).
* **Performance:** A targeted rebuild of a symbol with two aliases takes approximately **25 seconds**. Most of this time is spent scanning for missing data to ensure integrity, but I/O is strictly limited to the specified instruments.

---

### 📚 New & Updated Documentation

We have added several deep-dive guides to help you leverage the latest performance and adjustment features:

* **[Adjustments.md](adjustments.md)** – Implementation guide for Panama rolls, Dividends, and Multiplicative splits.
* **[Templates.md](templates.md)** – Guidelines for "God-tier" indicator performance using Polars/Rust to bypass the Python GIL.
* **[Code Examples](../config/plugins/indicators/)** – Direct reference for plugin and indicator development.


























