## Short term todo list

26-2: A change in priorization was made

Priorization:

- ML: Neuro-evolution sidetrack (experimental) -> finalize (see below) **
- Strip DuckDB
- Stabilization - Seeing if we can prevent OOM's and instead degrade in a "nicer way"
- Quality - Another full comparison pass on the indicators. LLM's can tell me they are fine but i want to SEE (TA-lib?).
- Coverage - Unit-testing > 80-90% + "Unhappy paths"
- Then split up - I have a testeable base then. K8S-readiness changes are not "minor changes".

[x] Initial refactor/preparation stage:
  - [x] Abstracting indicator registry
  - [x] Implementation get_data method (internal API)
  - [x] Minimalization of API 1.1 (no functionality strip)
  - [x] Strip of API 1.0
  - [x] Generic QA passes
  - [x] Initial performance tests. Did we lose, yes/no? Answer: no.
  - [x] Initial bug-checking (since a lot has moved)

Note: we are setup now to integrate the extensions below (weekend work).

Quality:
  - [x] ~~Users will try to export 1 million rows with market/volume profile.~~
  - [x] Multi-process API service for true concurrency
  - [x] Thread safety for MarketDataCache (calling get_data from multiple threads)
  - [x] Unit-test that does a performance-test on indicators with 10,000 records and warns on > 10ms.
  - [x] Aroon indicator is a PERFORMANCE-KILLER. Fix.
  - [x] Abstraction download-engine and HTTP/2 support (configurable)
  - [x] Eliminate the Polars->Pandas conversion in HTTP-api
  - [x] Allow get_data_auto to receive a polars Dataframe (and options)
  - [x] Use BTC-USD as heartbeat to detect open-candles, build indicator
  - [x] Support is-open indicator to detect the live-edge (open candles)
  - [ ] Support is-stale indicator to detect download/market-data issues
  - [ ] Degradation and change of execution mode on memory-pressure
  - [x] Extra quality pass on indicator kaufman-er and up (sort by modified desc)
  - [x] Automated validation of the system indicators using TA-lib where possible
  - [ ] More unit-tests NOW - in progress
  - [x] Find solution for UVLOOP WSL2 watchfiles CPU 100pct issue. Optionally, configurable.
  - [x] The panama and stock-split fixes
  - [x] Partial rebuilds eg `./rebuild-full.sh --symbol BRENT.CMD-USD-PANAMA` (plus their sources)
  - [ ] Third indicator execution path: CUDA/Rapids

Note: Cuda/Rapids/GPU: We were thinking "too advanced". Just implement it as a tensor operation. No chaining. Just in/out. Deploy first as an "experimental"-feature that is easy to grasp. Later we can see on advanced stuff. This path will be implemented to support inference better.

ML:
  - [ ] Validate CPU mode. Currently GPU focussed but users not having CUDA GPU should be able to run it as well.
  - [x] Implement an experimental version for sparse asymmetric bottom detection
  - [x] Test asymmetric bottom detection
  - [ ] Cleanup/Split major singularity class into parts. Generalize them. Make overloadable
  - [ ] Provide extension support for lenses (loss functions)
  - [ ] See what other activation functions, next to Gelu and Sigmoid, exist. Make configurable.
  - [ ] Revisit comet functionality. Make it support logs more properly.
  - [ ] Important: full forward test on NZDUSD, EURUSD and GBPUSD for "model 3750"
  - [ ] Add advanced diagnostics tools 
  - [ ] Fix scaling issues. Idea is to implement a zoom-alike approach (like in the interface, to amplify signals)
  - [ ] Harden
  - [-] 3x QA pass (1 done)

Note: this has, unexpectedly, become a very promising part of the system. It outperforms what i expected by magnitudes. Neuroevolution was the correct solution after standard RandomForest "failed" multiple times.

Modularity:
  - [ ] Split up ETL and have a central "feeder" engine that can distribute in near-realtime
  - [ ] Move resample to Polars

Early warning:
  - [ ] Warning/Reporting system for datasource outages

DAG Execution:
  - [x] ~~Directed Acyclic Graph for indicators~~
  - [x] ~~Virtual indicators~~
  - [x] ~~Dependency resolution~~
  - [x] Real parallel execution (via polars)

Note: strike-through of above is because get_data is powerful enough to handle dependencies

ASX:
  - [ ] Custom timeshifting

QuackQuack:
  - [ ] Eliminate DuckDB completely
  - [x] Panama prevents text-strip, invent solution for binary

Note: Sidetracking for symbols was implemented. We are now ready to strip DuckDB (feature 043)

Drawing/Visualization:
  - [x] Split JS to libs (chart.js, drawing.js, ui.js)
  - [ ] Drawing tools (lines, channels, fibs)
  - [x] Allow for line-color specification in the indicator (currently via custom.js)
  - [x] ~~Export to PNG/SVG?~~

Note: strike-through=wont do

[x] API Layer:
  - [X] Cross-asset queries
  - [X] Cross-timeframe queries
  - [x] Make internal API queryable from external code (bootstrapping)

[ ] TCP/Disk Layer
  - [ ] Columnar and io_uring
  - [ ] Apache Arrow Flight (research done ✔️)

Note: the HTTP API is nice but it has a major serialization tax

Example Indicator:
  - [x] ML integration example
  - [x] EUR-USD vs Bond Pearson correlation example
  - [x] Cross divergence example indicators
  - [x] Normalized ML indicators (they are overkill since ML engine normalizes itself but cannot delete them since users may already use them)
  - [ ] Add flags to certain indicators to "shift" bars to prevent lookahead bias in ML training

Note: Pearson was generalized and included as a system indicator. Furthermore cross-asset divergence examples were added to show divergences between assets for single column indicators (like RSI, SMA etc).

Note: I have custom indicators that eliminate lookahead bias. Eg on RSI, without the shift, the indicators peek in the "future". Generalize this functionality, using an additional argument, and share with users. Currently users should update their indicators themselves. 

Protection
  - [x] Circular indicator dependency protection (V1 present as a unit-test, V2 options checking todo)
  - [x] ~~Custom threadpool to optimize recursive get_data calls which use pandas indicators~~
  - [ ] OOM degradation

Note: Threadpool overload did not work. Same GIL issues. Waiting for 3.14t. Perhaps run an experiment. 3.14t is too difficult to install and use atm. I have it running but it involves a lot of manual compiling since not all wheels have been updated for the dependencies. I cannot put that burden on the users, so we wait a tiny bit longer. I don't think it's "useful" to write a script that does all the manual compilations. Too error-prone. If user encounters an error, maybe will not know what to do or how to proceed. Bad UX. Waiting is better option.

Testing:
  - [ ] Unit tests (80%+ coverage)
  - [x] Load tests
  - [ ] New performance benchmarks

Note: also cover the ML with unittests. ML is very tricky with respect to lookahead and leakage. First split up, while keeping in mind that te code should be testeable for potential lookahead/leakage (if possible). Still need to think on this.

Observability
  - [ ] Monitoring Health/Throughput/ROE
  - [ ] Normalized logging messages
  - [ ] Make a string-map for the ML log messages
  - [ ] "Additional stuff"

Note: better monitoring/normalized logging IS a requirement for K8S envs.

Note: currently the log messages of the ML are cosmic-themed. Most users will like, some will not. Map to a string table. Support dull as well. Minor prio.

Cleanup:
  - [ ] Builder cleanup
  - [ ] Remove CSV data layer
  - [ ] Update all documentation
  - [ ] Create migration guide
  - [ ] Final bug fix sweep

Rest
  - [x] Take a day off
  - [x] Take a second day off
  - [x] Take a third day off
  - [x] Take a fourth day off (26 feb)
  - [ ] Take a fifth day off


~~I know Istio too. Seeing if it's beneficial to build adapters (but this is medium term).~~ 
Moved to backlog.
