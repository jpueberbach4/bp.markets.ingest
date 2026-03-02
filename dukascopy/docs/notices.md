# ML

Ok. I have been playing with this all weekend. Here is the heads-up

- Is it useful? `Yes`
- What timeframe works this best on? `1d forex (only tested it there atm)`
- What assets are tested and confirmed?`BRENT-CMD-USD/1d, GBP-USD/1d, DEU.IDX-EUR/1d, BTC-USD/1d`
- What is the maximum accuracy you achieved? `86% (where the missing 14% are misses) on GBP-USD` 
- Is that in-sample, OOS-train, or truly OOS? `All 3 combined in a single scan (2025-NOW)`
- Are you happy? `Yes, worth the effort.`
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

Example diagnostics command:

```sh
./run-mldiag.sh --mode full --model checkpoints/model-best-gen12-f1-0.7692.pt \
--symbol GBP-USD --timeframe 1d --center example-pivot-finder_10_bottoms --threshold 0.23 \
--after 2025-01-01
```

Example outputs [here](../images/ml-example/logs).

This is not the end of the ML-experience. I will be doubling down on lower timeframes but 1d is the first target to get stable and it is already nearly at that. Documentation will come. In a somewhat similar style as `configuration.md`. From introduction, to concepts, to caveats, to guided most-complex asset configuration.

You need to know some stuff about tuning model parameters in the universes. How to penalize for non-precision, how to build a carpet bomber, what features to select, the generic thinking way behind all of this stuff. A seperate document will be created on how to extend the code.

Workflow will become this: Train → Diagnose → Deploy → Alert → Review → Execute

Give me a few days to write the stuff up. Will be like 4-5 A4 pages of information.

Next is:

- Additional tooling
- PNL testing
- Alerting
- Kinematics is deprecated. SRNN (Selective Recurring Neural Network) will be implemented instead.
- Indicator updates
- More asset-scanning/more tests

There are currently 3 example universes in the config folder.

- universe: BRENT/1d (you need to have it [panama-adjusted](adjustments.md))
- universe: GBP/1d
- universe: MilkyWay/4h (this one still needs tuning)

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




























