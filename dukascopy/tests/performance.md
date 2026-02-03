
## Actual tests


### The tests

```sh
Some of these tests are "ridiculous tests" but they are done to stress both horizontal (column) and vertical (row) limits.

3.000.000 records x 58 indicators, normal rolling SMA's (SMA250)

2: 3000000 records, time-passed: 3206.368039944209 ms + 58 indicators
shape: (3_000_000, 76)
┌─────────┬───────────┬───────────────┬─────────┬───┬──────────┬──────────┬──────────┬──────────┐
│ symbol  ┆ timeframe ┆ time_ms       ┆ open    ┆ … ┆ sma_235  ┆ sma_240  ┆ sma_245  ┆ sma_250  │
│ ---     ┆ ---       ┆ ---           ┆ ---     ┆   ┆ ---      ┆ ---      ┆ ---      ┆ ---      │
│ str     ┆ str       ┆ u64           ┆ f64     ┆   ┆ f64      ┆ f64      ┆ f64      ┆ f64      │
╞═════════╪═══════════╪═══════════════╪═════════╪═══╪══════════╪══════════╪══════════╪══════════╡
│ EUR-USD ┆ 1m        ┆ 1226948400000 ┆ 1.2724  ┆ … ┆ 1.266307 ┆ 1.266285 ┆ 1.266246 ┆ 1.266212 │
│ EUR-USD ┆ 1m        ┆ 1226948460000 ┆ 1.27265 ┆ … ┆ 1.26633  ┆ 1.266315 ┆ 1.266276 ┆ 1.266241 │
│ EUR-USD ┆ 1m        ┆ 1226948520000 ┆ 1.27165 ┆ … ┆ 1.266353 ┆ 1.266343 ┆ 1.266307 ┆ 1.26627  │
│ EUR-USD ┆ 1m        ┆ 1226948580000 ┆ 1.27185 ┆ … ┆ 1.266376 ┆ 1.266371 ┆ 1.266337 ┆ 1.2663   │
│ EUR-USD ┆ 1m        ┆ 1226948640000 ┆ 1.27195 ┆ … ┆ 1.266401 ┆ 1.266399 ┆ 1.266369 ┆ 1.26633  │
│ …       ┆ …         ┆ …             ┆ …       ┆ … ┆ …        ┆ …        ┆ …        ┆ …        │
│ EUR-USD ┆ 1m        ┆ 1480036080000 ┆ 1.05582 ┆ … ┆ 1.055375 ┆ 1.055373 ┆ 1.055373 ┆ 1.055375 │
│ EUR-USD ┆ 1m        ┆ 1480036140000 ┆ 1.05591 ┆ … ┆ 1.055378 ┆ 1.055376 ┆ 1.055375 ┆ 1.055377 │
│ EUR-USD ┆ 1m        ┆ 1480036200000 ┆ 1.05594 ┆ … ┆ 1.05538  ┆ 1.055378 ┆ 1.055378 ┆ 1.055379 │
│ EUR-USD ┆ 1m        ┆ 1480036260000 ┆ 1.05594 ┆ … ┆ 1.055383 ┆ 1.055381 ┆ 1.05538  ┆ 1.055381 │
│ EUR-USD ┆ 1m        ┆ 1480036320000 ┆ 1.05599 ┆ … ┆ 1.055385 ┆ 1.055384 ┆ 1.055383 ┆ 1.055383 │
└─────────┴───────────┴───────────────┴─────────┴───┴──────────┴──────────┴──────────┴──────────┘

1.000.000 records x 508 indicators, with long rolling SMA's (SMA2500)

2: 1000000 records, time-passed: 1429.5939080184326 ms + 508 indicators
shape: (1_000_000, 526)
┌─────────┬───────────┬───────────────┬─────────┬───┬──────────┬──────────┬──────────┬──────────┐
│ symbol  ┆ timeframe ┆ time_ms       ┆ open    ┆ … ┆ sma_2485 ┆ sma_2490 ┆ sma_2495 ┆ sma_2500 │
│ ---     ┆ ---       ┆ ---           ┆ ---     ┆   ┆ ---      ┆ ---      ┆ ---      ┆ ---      │
│ str     ┆ str       ┆ u64           ┆ f64     ┆   ┆ f64      ┆ f64      ┆ f64      ┆ f64      │
╞═════════╪═══════════╪═══════════════╪═════════╪═══╪══════════╪══════════╪══════════╪══════════╡
│ EUR-USD ┆ 1m        ┆ 1668711600000 ┆ 1.03388 ┆ … ┆ 1.0376   ┆ 1.037593 ┆ 1.037587 ┆ 1.037582 │
│ EUR-USD ┆ 1m        ┆ 1668711660000 ┆ 1.03459 ┆ … ┆ 1.0376   ┆ 1.037593 ┆ 1.037587 ┆ 1.037582 │
│ EUR-USD ┆ 1m        ┆ 1668711720000 ┆ 1.03423 ┆ … ┆ 1.0376   ┆ 1.037593 ┆ 1.037587 ┆ 1.037582 │
│ EUR-USD ┆ 1m        ┆ 1668711780000 ┆ 1.03456 ┆ … ┆ 1.0376   ┆ 1.037593 ┆ 1.037587 ┆ 1.037582 │
│ EUR-USD ┆ 1m        ┆ 1668711840000 ┆ 1.03468 ┆ … ┆ 1.0376   ┆ 1.037594 ┆ 1.037587 ┆ 1.037581 │
│ …       ┆ …         ┆ …             ┆ …       ┆ … ┆ …        ┆ …        ┆ …        ┆ …        │
│ EUR-USD ┆ 1m        ┆ 1754274120000 ┆ 1.1581  ┆ … ┆ 1.146013 ┆ 1.146008 ┆ 1.146002 ┆ 1.145997 │
│ EUR-USD ┆ 1m        ┆ 1754274180000 ┆ 1.15812 ┆ … ┆ 1.146019 ┆ 1.146014 ┆ 1.146008 ┆ 1.146003 │
│ EUR-USD ┆ 1m        ┆ 1754274240000 ┆ 1.15808 ┆ … ┆ 1.146025 ┆ 1.146019 ┆ 1.146014 ┆ 1.146009 │
│ EUR-USD ┆ 1m        ┆ 1754274300000 ┆ 1.15798 ┆ … ┆ 1.14603  ┆ 1.146025 ┆ 1.14602  ┆ 1.146014 │
│ EUR-USD ┆ 1m        ┆ 1754274360000 ┆ 1.15802 ┆ … ┆ 1.146036 ┆ 1.146031 ┆ 1.146026 ┆ 1.14602  │
└─────────┴───────────┴───────────────┴─────────┴───┴──────────┴──────────┴──────────┴──────────┘

100.000 records x 3508 indicators, with extreme long rolling SMA's (SMA17500)

2: 100000 records, time-passed: 1792.6002560416237 ms + 3508 indicators
shape: (100_000, 3_526)
┌─────────┬───────────┬───────────────┬─────────┬───┬───────────┬───────────┬───────────┬───────────┐
│ symbol  ┆ timeframe ┆ time_ms       ┆ open    ┆ … ┆ sma_17485 ┆ sma_17490 ┆ sma_17495 ┆ sma_17500 │
│ ---     ┆ ---       ┆ ---           ┆ ---     ┆   ┆ ---       ┆ ---       ┆ ---       ┆ ---       │
│ str     ┆ str       ┆ u64           ┆ f64     ┆   ┆ f64       ┆ f64       ┆ f64       ┆ f64       │
╞═════════╪═══════════╪═══════════════╪═════════╪═══╪═══════════╪═══════════╪═══════════╪═══════════╡
│ EUR-USD ┆ 1m        ┆ 1668711600000 ┆ 1.03388 ┆ … ┆ 1.009642  ┆ 1.009637  ┆ 1.009632  ┆ 1.009628  │
│ EUR-USD ┆ 1m        ┆ 1668711660000 ┆ 1.03459 ┆ … ┆ 1.009644  ┆ 1.009639  ┆ 1.009635  ┆ 1.00963   │
│ EUR-USD ┆ 1m        ┆ 1668711720000 ┆ 1.03423 ┆ … ┆ 1.009646  ┆ 1.009642  ┆ 1.009637  ┆ 1.009632  │
│ EUR-USD ┆ 1m        ┆ 1668711780000 ┆ 1.03456 ┆ … ┆ 1.009649  ┆ 1.009644  ┆ 1.009639  ┆ 1.009635  │
│ EUR-USD ┆ 1m        ┆ 1668711840000 ┆ 1.03468 ┆ … ┆ 1.009651  ┆ 1.009646  ┆ 1.009642  ┆ 1.009637  │
│ …       ┆ …         ┆ …             ┆ …       ┆ … ┆ …         ┆ …         ┆ …         ┆ …         │
│ EUR-USD ┆ 1m        ┆ 1677165000000 ┆ 1.06128 ┆ … ┆ 1.06923   ┆ 1.06923   ┆ 1.06923   ┆ 1.069231  │
│ EUR-USD ┆ 1m        ┆ 1677165060000 ┆ 1.06145 ┆ … ┆ 1.069229  ┆ 1.069229  ┆ 1.06923   ┆ 1.06923   │
│ EUR-USD ┆ 1m        ┆ 1677165120000 ┆ 1.06152 ┆ … ┆ 1.069229  ┆ 1.069229  ┆ 1.069229  ┆ 1.06923   │
│ EUR-USD ┆ 1m        ┆ 1677165180000 ┆ 1.06168 ┆ … ┆ 1.069228  ┆ 1.069228  ┆ 1.069229  ┆ 1.069229  │
│ EUR-USD ┆ 1m        ┆ 1677165240000 ┆ 1.06165 ┆ … ┆ 1.069227  ┆ 1.069228  ┆ 1.069228  ┆ 1.069229  │
└─────────┴───────────┴───────────────┴─────────┴───┴───────────┴───────────┴───────────┴───────────┘


50.000 records x 5008 indicators, with insane long rolling SMA's (SMA25000)

1: 50000 records, time-passed: 2902.5675889570266 ms + 5008 indicators
shape: (50_000, 5_026)
┌─────────┬───────────┬───────────────┬─────────┬───┬───────────┬───────────┬───────────┬───────────┐
│ symbol  ┆ timeframe ┆ time_ms       ┆ open    ┆ … ┆ sma_24985 ┆ sma_24990 ┆ sma_24995 ┆ sma_25000 │
│ ---     ┆ ---       ┆ ---           ┆ ---     ┆   ┆ ---       ┆ ---       ┆ ---       ┆ ---       │
│ str     ┆ str       ┆ u64           ┆ f64     ┆   ┆ f64       ┆ f64       ┆ f64       ┆ f64       │
╞═════════╪═══════════╪═══════════════╪═════════╪═══╪═══════════╪═══════════╪═══════════╪═══════════╡
│ EUR-USD ┆ 1m        ┆ 1668711600000 ┆ 1.03388 ┆ … ┆ 1.005739  ┆ 1.005736  ┆ 1.005732  ┆ 1.005728  │
│ EUR-USD ┆ 1m        ┆ 1668711660000 ┆ 1.03459 ┆ … ┆ 1.005741  ┆ 1.005738  ┆ 1.005734  ┆ 1.00573   │
│ EUR-USD ┆ 1m        ┆ 1668711720000 ┆ 1.03423 ┆ … ┆ 1.005743  ┆ 1.00574   ┆ 1.005736  ┆ 1.005732  │
│ EUR-USD ┆ 1m        ┆ 1668711780000 ┆ 1.03456 ┆ … ┆ 1.005745  ┆ 1.005741  ┆ 1.005738  ┆ 1.005734  │
│ EUR-USD ┆ 1m        ┆ 1668711840000 ┆ 1.03468 ┆ … ┆ 1.005747  ┆ 1.005743  ┆ 1.00574   ┆ 1.005736  │
│ …       ┆ …         ┆ …             ┆ …       ┆ … ┆ …         ┆ …         ┆ …         ┆ …         │
│ EUR-USD ┆ 1m        ┆ 1672938720000 ┆ 1.05414 ┆ … ┆ 1.062664  ┆ 1.062663  ┆ 1.062661  ┆ 1.06266   │
│ EUR-USD ┆ 1m        ┆ 1672938780000 ┆ 1.05447 ┆ … ┆ 1.062664  ┆ 1.062663  ┆ 1.062661  ┆ 1.06266   │
│ EUR-USD ┆ 1m        ┆ 1672938840000 ┆ 1.05434 ┆ … ┆ 1.062664  ┆ 1.062663  ┆ 1.062661  ┆ 1.06266   │
│ EUR-USD ┆ 1m        ┆ 1672938900000 ┆ 1.05428 ┆ … ┆ 1.062664  ┆ 1.062663  ┆ 1.062661  ┆ 1.06266   │
│ EUR-USD ┆ 1m        ┆ 1672938960000 ┆ 1.0539  ┆ … ┆ 1.062664  ┆ 1.062663  ┆ 1.062661  ┆ 1.062659  │
└─────────┴───────────┴───────────────┴─────────┴───┴───────────┴───────────┴───────────┴───────────┘


Beyond that... going higher than 5000 indicators. The system really is struggling. 

Summarized:

Test	Rows	    Columns	    Indicators	Max SMA Period	Time	Total Values	Values/sec
1	    3,000,000   76          58          250             3.21s	228M            71M/sec
2	    1,000,000	526	        508	        2,500	        1.43s	526M	        368M/sec
3	      100,000	3,526	    3,508	    17,500	        1.79s	353M	        197M/sec
4	       50,000	5,026	    5,008	    25,000	        2.90s	251M	        86M/sec
```

Conclusion? There's a sweet spot around 1M rows × 500 columns where the system achieves maximum throughput (368M values/sec).
It makes sense to optimize for optimal row and column counts. Test what gives highest throughput.

For most users anything will work but if you are indicator/feature-heavy, this is the advice.

PS ofcourse this is related to what indicators you use. Its not the best test.

### The Breakdown

**1. The Sweet Spot (Test 2)**
* **Throughput:** `2.94 GB/s`
* **Configuration:** 1,000,000 Rows × 526 Columns
* **Analysis:** This matches the "Price Only" API speed (~2.5 GB/s) almost exactly. This represents the hardware's **Physical Limit**; data cannot be moved in/out of RAM faster than this on the current machine.
* **Why 1M rows?**
    * 1 Million rows × 8 bytes ≈ **8MB**.
    * This fits perfectly into the **L3 Cache** of modern high-performance laptop CPUs (typically 12MB–24MB).
    * The CPU processes the entire chunk without waiting for main RAM, maximizing throughput.

**2. Long & Thin (Test 1)**
* **Throughput:** `0.57 GB/s`
* **Configuration:** 3,000,000 Rows × 76 Columns
* **Analysis:** Significantly slower due to **Cache Thrashing**.
    * At 3M rows, the column vectors overflow the L3 cache.
    * The CPU is forced to constantly evict data and fetch the next chunk from slower RAM, destroying performance.

**3. Wide & Ultra-Wide (Test 3 & 4)**
* **Throughput:** `1.57 GB/s` → `0.69 GB/s`
* **Configuration:** 100k–50k Rows × 3,500–5,000 Columns
* **Analysis:** The "Stride" Problem.
    * With 5,000 columns, a single "row" of data is **40 KB** wide.
    * While input reading (Columnar) is fast, maintaining the *output* matrix for 5,000 columns creates massive memory pressure.
    * The memory controller is forced to manage thousands of active write streams simultaneously, saturating bandwidth.

### Conclusion: The "Golden Number"

**1 Million Rows** is the optimal chunk size for this architecture for a Ryzen 7.