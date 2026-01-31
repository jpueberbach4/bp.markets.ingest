## Table of Contents

- [What Is This Tool Used For?](#what-is-this-tool-used-for)
- [Server Kindness](#server-kindness)
- [Key Design Principles](docs/architecture.md#key-design-principles)
- [Quick Start](#quick-start)
  - Dependencies & Installation
  - Directory Permissions
  - First Run & Incremental Mode
  - Automatic Updates (cron)
- [Initial Configuration](#symbols-configuration)
  - Adding New Symbols
- [Advanded Configuration](docs/configuration.md#pipeline-configuration-v03-and-above)
  - Overriding timeframes, etc
- [Output schema](docs/architecture.md#output-schema)
  - Details on generated files
- [Quick Check](#quick-check)
- [Converter and Panama](docs/tools.md#parquetcsv-export-v04-and-above)
  - Details on CSV->Parquet conversion
- [HTTP API service](docs/http.md)
  - Details on HTTP API
- [Fail-Fast](docs/architecture.md#fail-fast)
- [Directory Structure](docs/architecture.md#directory-structure)
- [Troubleshooting](docs/troubleshooting.md)
  - Stale Locks
  - Full Rebuild
  - Alignment
  - **Rate limits applied**
- [Future Work](docs/future.md)
- [DuckDB (Advanced)](docs/tools.md#duckdb-advanced-users)
- [Final Word](#final-word)
- [Terms of use](#terms-of-use)
- [License](#license)

---

## What Is This Tool Used For?

>BP-Markets is a high-performance, local-first data bridge built for indie traders. Unlike cloud-based solutions, it is optimized for zero-latency local execution, allowing your trading terminal and data API to run side by side without resource contention. \
\
The system incrementally updates market data, resampling completed 1-minute candles into a set of default higher timeframes that can be customized globally or per symbol. It also tracks open higher-timeframe candles, which can optionally be excluded through modifiers. \
\
Data can be queried or constructed directly from a WSL2 terminal or via an HTTP API service. Designed by a trader, for traders, BP-Markets focuses on performance, accuracy, and workflow efficiency. Future releases will introduce high-performance backtesting capabilities that fully eliminate lookahead bias. \
\
The tool features a customizable, advanced (hybrid) indicator engine and uses an internal API to query data across assets and timeframes, including access to indicator values from other instruments. Indicators can be expressed as Polars-expressions or implemented on Pandas dataframes directly. \
\
Any modern laptop having NVMe will do. Storage requirements are about 1 GB per configured symbol. \
\
The code-base is small and heavily documented. This is a high-performance system. \
\
Note: This is not a click-and-go or “magical” project. It’s intended for data preparation to support downstream analysis, such as machine learning. You can use it to test and design indicators or to extract inter-asset features for ML workflows—that’s how I use it. While indicator-integrated data can be extracted, that is not the primary purpose of this project. You will need to know Python if you want to use this project efficiently. \
\
I will be adding (more) examples for integration with other Python projects, Excel, Jupyter notebooks and Ensemble-learning (ML) while I am developing this project. This project is not even close to "finished". There is still a lot of work to do. \
\
One more thing: there has been a discussion to take the project private and continue advanced features in a private setting. Some users may have read this a little while ago. This is off-the-table. Development will continue to be public.

Example 20 year chart of EUR-USD:

![Example GBPUSD](images/examplevieweurusd.png)

Historical market data can be leveraged in multiple ways to enhance analysis, decision-making, and trading performance:

- **Backtesting** → Evaluate and refine trading strategies by simulating them on past market conditions. This helps determine whether a strategy is robust, profitable, and resilient across different market environments.

- **Technical Analysis** → Use historical charts to identify trends, chart patterns, support- and resistance levels. You can also perform correlation studies to compare long-term relationships between currency pairs or other assets.

- **Seasonal Analysis** → Detect recurring market behaviors or unusual pricing patterns that tend to appear during specific months, weeks, or seasons.

- **Volatility Assessment** → Analyze historical volatility to adjust risk parameters, optimize position sizing, and set more accurate stop-loss levels.

- **Computational Intelligence** → Build machine-learning or statistical models trained on historical price data to forecast potential market movements.

- **Economic Event Impact** → Study how past economic releases, geopolitical events, and news shocks influenced currency pairs — helping you prepare for similar situations in the future.

---

## Server Kindness

[Dukascopy SA](https://www.dukascopy.com) has been providing this priceless data **for free since 2003** with no paywall and no API key. This entire pipeline only exists because of their generosity.

If you find this tool useful, please consider:

- Trying their platform (I’ve been a happy client for years — support is actually human and fast)
- Running the script no more than once per hour unless you truly need minute-level updates

These two small acts keep the data flowing for everyone, forever.
Thank you — and thank you, Dukascopy.

---

## Quick start

Clone the repository

```
git clone https://github.com/jpueberbach4/bp.markets.ingest.git
cd bp.markets.ingest/dukascopy
```

Make sure python version is 3.8+. 

```sh
python3 --version
```

For this Dukascopy Data Pipeline project, the Python dependencies that need to be installed via pip are:

| Package               | Version      | Purpose                                                                 |
|:----------------------|:-------------|:------------------------------------------------------------------------|
| `pyyaml`              | >= 6.0.1     | High-speed YAML configuration parsing (LibYAML)                         |
| `backports.zoneinfo`  | < 3.9        | Efficient timezone support for Python 3.8 environments                  |
| `duckdb`              | >= 1.1.0     | Analytical database layer and Parquet building helper                   |
| `pandas`              | >= 2.0.3     | CSV I/O, data manipulation, and incremental loading                    |
| `numpy`               | >= 1.24.4    | Vectorized numeric computations and OHLC calculations                   |
| `orjson`              | >= 3.10.15   | Ultra-fast JSON parsing for delta-encoded data                          |
| `requests`            | >= 2.22.0    | Reliable download of raw data via HTTP                                  |
| `tqdm`                | >= 4.67.1    | Low-overhead progress bars for long-running loops                       |
| `filelock`            | >= 3.16.1    | Process-safe locking to prevent parallel race conditions                |
| `uvicorn`             | >= 0.33.0    | High-performance ASGI server for the local API                          |
| `uvloop`              | >= 0.22.1    | C-based asyncio event loop (Linux/macOS speedups)                       |
| `httptools`           | >= 0.6.4     | High-speed C-based HTTP parser for Uvicorn                              |
| `fastapi`             | >= 0.124.4   | Modern, fast web framework for the local service                         |
| `fastjsonschema`      | >= 2.21.2    | Pre-compiled JSON schema validation for config speed                    |

Install with:

```sh
./setup-dukascopy.sh
```

**Permissions**

These scripts read from and write to both the data directory and the cache directory. If your system uses strict permission settings, ensure that the ./data and ./cache directory are created in advance.

```sh
mkdir -p ./data ./cache
chown -R $USER:$USER ./data ./cache
chmod u+rwx ./data ./cache
```
---

Configure your symbols as shown in the next section of this readme.

>[Symbols Configuration](#symbols-configuration)

Next, run the pipeline with:

```sh
./rebuild-full.sh
```

Optionally, configure a cronjob for periodical execution: 

```sh
crontab -e
```

Add the following line, adjust path accordingly-run once every 15m:

```sh
*/15 * * * * sleep $(( (RANDOM \% 27) + 5 )) && cd /home/jpueberb/repos2/bp.markets.ingest/dukascopy && ./run.sh
```

In order to get the highest possible performance, I recommend to toggle ALL the `fmode` fields in `config.user.yaml` to `binary`. This is considered as "a custom change". When you make custom changes, you cannot use `./setup-dukascopy.sh` anymore since this script will restore the settings back to "text"-this will change in the future now CSV mode is deprecated.

* For configuration of custom timeframes, sessions etc, [see here](docs/configuration.md)
* For more information on the binary format, [see here](docs/binary.md)
* For more information on the HTTP API service, [see here](docs/http.md)
* For more information on Parquet/CSV building, [see here](docs/tools.md)
* For data accuracy information, [see here](docs/tests.md)
* For latest updates, announcements etc, [see here](docs/notices.md)

---

## Symbols Configuration

This project includes a symbols.txt file, which is a single-column CSV containing symbol identifiers.
If you wish to override this default list of symbols

```sh
cp symbols.txt symbols.user.txt
```

Next edit symbols.user.txt to include your symbols of interest (symbols.user.txt is in .gitignore). 

---

All symbols supported by the Dukascopy API are available, with no restrictions. 

Please see here for a complete symbol list:

[Dukascopy historical download](https://www.dukascopy.com/swiss/english/marketwatch/historical/)

**Example**. Suppose we want to add **EUR/MXN** to our setup. We visit the link above and copy the symbol name exactly as shown in the screenshot below.

![Dukascopy download screenshot](images/dukascopysymbols.png)

We stop our crontab service for a moment or comment the line for `run.sh` in crontab. Next, we add the symbol as a new row in symbols.user.txt. Next, run the pipeline using:

The pipeline will begin downloading the symbol's historical data (this may take some time) and then execute the remaining steps.

The new symbol is now added and will be updated automatically during each incremental run.

>When you don't stop the crontab periodic execution before changing the symbol list, you will need to ```rebuild-full.sh```!

---

## Quick check

For users who are just getting started, or for those who want a quick way to validate their generated data:


Start your localized HTTP API service

```sh
./service.sh start
```

Now open in a browser:

```sh
http://localhost:8000
```

It will show you your localized data.

---

## Final word

Thank you for using this toolkit. The goal of the project is simple: provide a fast and fully transparent pipeline for high-quality historical market data. **This architecture prioritizes speed through binary formats.** If you have ideas, find issues, or want to contribute, feel free to open a GitHub issue or pull request.

A more advanced, tick-ready successor—planned as a C++ DuckDB extension—is under development and will be announced when ready.

## Terms of Use

**Acceptance Required Before First Use**

### 1. Data Source & Attribution
- Data originates from Dukascopy Bank SA ([www.dukascopy.com](https://live-login.dukascopy.com/rto3/))
- You must respect [Dukascopy's Terms of Service](https://www.dukascopy.com/swiss/english/legal-pages/terms-of-use/)

### 2. Strict Usage Restrictions

- **PERSONAL, NON-COMMERCIAL USE ONLY**
- **NO REDISTRIBUTION** in any form (raw, processed, aggregated, derived, Parquet, CSV, etc.)
- **NO INCORPORATION** into commercial products, services, or platforms
- **NO PUBLIC HOSTING** (GitHub, Hugging Face, Kaggle, cloud storage, torrents, datasets)
- **NO AUTOMATED BULK EXTRACTION** (wildcards intentionally disabled)

### 3. Your Responsibilities

- You accept ALL liability for your usage
- You indemnify the developer against any claims
- You use at your own risk
- You respect server resources (rate limits enforced)

### 4. Developer Disclaimer

- Not affiliated with Dukascopy Bank SA
- Software provided "as is" - no warranty
- For educational/research purposes only
- Not trading/investment advice

### 5. Consequences of Violation

- Repository takedown
- Loss of free data access for everyone

---

## License

This software is licensed under the MIT License.

Copyright JP Ueberbach, 2025

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Dukascopy Ready](https://img.shields.io/badge/Dukascopy-Ready-006400?style=flat&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJ3aGl0ZSI+PHBhdGggZD0iTTEyIDJDNi40OCAyIDIgNi40OCAyIDEyczQuNDggMTAgMTAgMTAgMTAtNC40OCAxMC0xMFMxNy41MiAyIDEyIDJ6bTAgMThjLTQuNDEgMC04LTMuNTktOC04czMuNTktOCA4LTggOCAzLjU5IDggOC0zLjU5IDgtOCA4eiIvPjxwYXRoIGQ9Ik0xNi4yIDkuNEwxMiAxMmw0LjIgMi42bC0yLjYgNC4ybC0yLjYtMi42LTQuMiAyLjZ2LTIuNi00LjJ6Ii8+PC9zdmc+)




