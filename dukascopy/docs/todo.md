## Short term todo list

Priorization:

- Stabilization - Seeing if we can prevent OOM's and instead degrade in a "nicer way"
- Quality - Another full comparison pass on the indicators. LLM's can tell me they are fine but i want to SEE (TA-lib?).
- Coverage - Unit-testing > 80-90% + "Unhappy paths"
- Panama-adjusted sidetracked data plus stocksplit support. Two in one solution.
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
  - [x] Multi-process API service for true concurrency
  - [x] Unit-test that does a performance-test on indicators with 10,000 records and warns on > 10ms.
  - [ ] Aroon indicator is a PERFORMANCE-KILLER. Fix.
  - [x] Abstraction download-engine and HTTP/2 support (configurable)
  - [x] Eliminate the Polars->Pandas conversion in HTTP-api
  - [x] Allow get_data_auto to receive a polars Dataframe (and options)
  - [x] Use BTC-USD as heartbeat to detect open-candles, build indicator
  - [ ] Degradation and change of execution mode on memory-pressure
  - [x] Extra quality pass on indicator kaufman-er and up (sort by modified desc)
  - [x] Automated validation of the system indicators using TA-lib where possible
  - [ ] More unit-tests NOW - in progress
  - [x] Find solution for UVLOOP WSL2 watchfiles CPU 100pct issue. Optionally, configurable.
  - [ ] Third indicator execution path: CUDA/Rapids. I need to know this for ML. Can I gain with it?

Note: UVLOOP WSL2 fix was implemented through a config.user.yaml setting.

Note: Cuda/Rapids/GPU: The "Elegant" Fix: Use a Coalescing Buffer. Instead of immediate execution, the internal API should collect indicator requests within a tiny time window (e.g., 5-10ms) or until a batch size is met, then ship one massive Arrow table to the GPU. This maximizes the O(1) nature of the parallel execution. Could be too much for now. If too much: it moves down the feature-list.

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

DuckDB:
  - [ ] Eliminate completely

Panama:
  - [ ] Panama prevents text-strip, invent solution for binary

Drawing/Visualization:
  - [x] Split JS to libs (chart.js, drawing.js, ui.js)
  - [ ] Drawing tools (lines, channels, fibs)
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
  - [ ] EUR-USD vs Bond Pearson correlation example

Protection
  - [x] Circular indicator dependency protection (V1 present as a unit-test, V2 options checking todo)
  - [ ] Custom threadpool to optimize recursive get_data calls which use pandas indicators

Testing:
  - [ ] Unit tests (80%+ coverage)
  - [x] Load tests
  - [ ] New performance benchmarks

Observability
  - [ ] Monitoring Health/Throughput/ROE
  - [ ] Normalized logging messages
  - [ ] "Additional stuff"

Note: better monitoring/normalized logging IS a requirement for K8S envs.

Cleanup:
  - [ ] Builder cleanup
  - [ ] Remove CSV data layer
  - [ ] Update all documentation
  - [ ] Create migration guide
  - [ ] Final bug fix sweep

Rest
  - [x] Take a day off
  - [x] Take a second day off
  - [ ] Take a third day off


I know Istio too. Seeing if it's beneficial to build adapters (but this is medium term).
