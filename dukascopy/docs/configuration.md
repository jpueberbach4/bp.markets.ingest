## Pipeline Configuration (v0.5 and above)

This section describes the configuration of this project. It focusses mainly on how to get your setup inline with your metatrader platform of choice. We will work through it through examples. Purpose of this information is to get you able to configure assets yourself without any help.

First the concepts.

**Symbols**

A symbol is an instrument-specific configuration scope. It acts as the primary identifier for a financial asset (e.g., AAPL.US-USD, XAU-USD, or SGD.IDX-SGD) and serves as the bridge between raw market data and the application of localized processing rules. In the configuration hierarchy, the symbol-scope sits between the global defaults and the session-specific overrides, allowing for precise control over how individual assets are handled by the pipeline.

**Timezones**

A timezone is a temporal offset configuration. It defines how the system "shifts" incoming market data—which is natively in UTC (GMT)—to align with the target display time, such as an MT4 server. Since UTC is static and does not observe seasonal shifts, the timezone configuration dynamically manages the transition between GMT+2 (Winter) and GMT+3 (Summer). This logic typically follows the America/New_York DST/STD calendar to ensure that daily candle closes remain consistent throughout the year.

**Timeframes**

A timeframe is an aggregation definition. It specifies the duration used to group incoming source data (e.g., 1-minute ticks) into larger candles (e.g., 1-hour or 4-hour blocks). Timeframes are configured hierarchically within the system: they can be defined at the global-scope, symbol-scope, or session-scope. Settings follow a strict inheritance model where the session-scope inherits from the symbol-scope, and the symbol-scope inherits from the global-scope (defaults).

**Origins**

An origin is an alignment anchor. It defines the exact reference point in time from which the aggregation grid is calculated. While a timeframe determines the size of the bucket, the origin determines the placement of the first bucket (where the grid begins). This ensures that candles "snap" to specific moments, such as an exchange's opening bell. Like timeframes, the origin can be defined at the global-scope, symbol-scope, or session-scope, and follows the same inheritance logic.

**Sessions**

A session is a temporal boundary definition. It specifies the active trading windows and date ranges during which specific resampling rules are applied to an instrument. Sessions represent the most granular level in the configuration hierarchy, allowing for specialized handling of market hours—such as morning sessions, after-hours trading, or "ancient" historical periods with legacy alignment policies.

**Includes**

An include is a modular configuration directive. It tells the system to inject settings from external files into the current configuration at a specific location. By using includes, you can break a massive, complex configuration into smaller, manageable chunks that are logically separated by asset class, region, or functionality.

And finally,...

**Post-processing**

Post-processing is a data-refinement layer. It defines a set of transformation rules that are applied to candles after they have been aggregated from the source, but before they are committed to the final dataset. While standard resampling handles the basic grouping of data, post-processing allows for surgical adjustments to fix platform-specific inconsistencies, handle "out-of-market" data points, and ensure the final chart output matches a specific broker's visual logic. Pre-processing is at this time not needed - and thus not implemented.

---

Now that the core definitions are established, we will demonstrate how to configure a symbol with custom sessions and determine the appropriate alignment settings. For this walkthrough, we will use the most complex asset in the current pipeline: SGD.IDX-SGD (the Singapore stock index). We will approach this scenario as a "from-scratch" implementation, assuming no prior configuration exists.

**First step:** Symbol discovery and registration

To begin the integration, you must first identify the unique symbol identifier as defined by the data provider. Since the specific naming convention for the Singapore Index is unknown, navigate to the [Dukascopy Historical Data Portal](https://www.dukascopy.com/swiss/english/marketwatch/historical/). Under the "Indices CFD" category, locate the "Singapore Blue Chip Index" to retrieve its exact symbol name: SGD.IDX/SGD.

Once identified, the instrument must be registered within the system's symbol-scope. Open the symbols.user.txt file in a text editor and add SGD.IDX/SGD as a new entry. This registration acts as the entry point for the data pipeline, allowing the orchestrator to recognize the asset and begin applying the inherited timezone, timeframe, and session configurations defined in your YAML includes.

**Second step:** Session and Timezone Discovery

Once the symbol is registered, the next step is to define its session boundaries and timezone offset. To ensure high-fidelity resampling, you must identify the exact trading windows for the futures or CFD contract. You can utilize an AI partner like Gemini to extract this data by asking: "What are the futures/CFD trading session times for the Singapore index? Please list them in a table."

The resulting data will define the gatekeeper logic for your configuration:

  | Session | from | to | Description |
  |---------|------|----|-------------|
  | T Session  |	08:30 | 17:20 |	The main daytime trading session. |
  | T+1 Session	| 17:50	| 05:15 | The "After-Hours" overnight session. |

**Third step:** Origin Calibration via MetaTrader

An origin calibration is the process of synchronizing your aggregation grid with the actual candle timestamps of your target platform. Because brokers use different server times (often $GMT+2$ or $GMT+3$), you must manually verify the "anchor times" displayed in MetaTrader 4 (MT4) to ensure your configuration accurately replicates the chart's visual structure.

- Identify the Target Chart: Open your MT4 terminal and load the 4H (H4) chart for the Singapore Index (SGD.IDX-SGD).
- Target Stable Data: Scroll back to the final days of December of any year. This ensures you are viewing "Winter Time" data, which is the standard baseline for many $GMT+2$ server configurations.
- Inspect the Anchor Times: Move your mouse pointer over the candles. A layout overlay will appear showing the specific pricing information and, most importantly, the timestamp.
- Extract the "HH" Values: You will notice candles starting at two distinct minute marks: HH:30 and HH:50.
  - The T-Session Anchor: Locate the first occurrence of an HH:30 candle in a day. In the case of the Singapore Index, you will find this is 02:30.
  - The T+1 Session Anchor: Locate the first occurrence of an HH:50 candle. For this instrument, the anchor is 15:51. (Note: Use the exact minutes shown, even if they seem non-standard).

**Fourth step:** Timezone Identification

The final piece of the data puzzle is identifying the correct timezone identifier. This ensures the system interprets the exchange’s "08:30" as a specific point in global time, preventing your candles from shifting when market hours are processed.

You can use Gemini to confirm this by asking: "What is the IANA timezone identifier for the Singapore Index?" It will confirm the correct string: ```Asia/Singapore```

**Fifth step:** Symbol Configuration

Now that you have acquired all the necessary metadata—the symbol name, the sessions, the timezone, and the origins—you are ready to implement the configuration.

Following the system’s modular architecture, you will add a new YAML file to the config.user/dukascopy/timeframes/indices directory using an include-friendly naming convention. Since this index is traded in Singapore Dollars, create a file named SGD-indices.yaml. I won't go into further details on what to specify, since the example is already configured. See example.

**Sixth step:** Historical Validation

The goal of validation is to determine if the session behavior has remained consistent throughout history or if "candle alignment policy" changes have occurred over time. Market exchanges and brokers occasionally update their schedules or the way they group data, which can create "drift" in your historical backtests if not accounted for.

- Inspect Historical Anchors: Open MT4 and load the 4H chart for the Singapore Index. Hold down the Page Up key to scroll back to the earliest available data.

- Detect Alignment Shifts: Examine the candle timestamps at different points in the past (a good rule of thumb is to check a few weeks for every year). If you notice that the origins (the HH:30 or HH:50 marks) have shifted to a different time, you have identified a policy change.

- Locate the "Switch Point": Pinpoint the exact date and time when the alignment changed. This process requires a bit of manual "scrolling-and-checking," but it is vital for ensuring your post-processing logic remains accurate across decades of data.

- Normalize the Timestamp: For the Singapore Index, a major policy shift occurred on August 7, 2022. Since your MT4 chart displays server time (GMT+2/3), use an AI partner like Gemini to convert that specific moment into Asia/Singapore time.

In your configuration, this "Switch Point" is defined using the from_date and to_date fields within the sessions block. This allows the system to apply "Ancient" rules to the historical data and "Modern" rules to recent data, ensuring seamless continuity across the entire dataset.

**Seventh step:** Building the dataset

Perform a full rebuild using ```./rebuild-full.sh```

**Note: This is the most complex asset-type to configure. Once you master the logic behind this instrument, the rest of the catalog becomes straightforward.**

For the vast majority of assets, you will find that the origin alignment remains constant. This is typically because the asset strictly follows the US market calendar or because it does not observe shifts at all—as is the case with Forex. Because Forex is temporally static, you will notice it rarely requires custom symbol-scope configurations; these instruments simply inherit the system's global defaults.

There are already extensive configuration examples available within the config/ directories. If you are using the Dukascopy MT4 server, you will likely find that most assets of interest are already pre-configured. 

To setup for general MT4 and/or Dukascopy MT4, the only thing you need to do is to execute ```./setup-dukascopy.sh```.

The main configuration file ```config.yaml``` or ```config.user.yaml``` is pretty self-explanatory. Good luck!
