## Short term todo list

[x] Initial refactor/preparation stage:
  - [x] Abstracting indicator registry
  - [x] Implementation get_data method (internal API)
  - [x] Minimalization of API 1.1 (no functionality strip)
  - [x] Strip of API 1.0
  - [x] Generic QA passes
  - [x] Initial performance tests. Did we lose, yes/no? Answer: no.
  - [x] Initial bug-checking (since a lot has moved)

Note: we are setup now to integrate the extensions below (weekend work).

DAG Execution:
  - [x] ~~Directed Acyclic Graph for indicators~~
  - [x] ~~Virtual indicators~~
  - [x] ~~Dependency resolution~~
  - [ ] Real parallel execution

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

Example Indicator:
  - [x] ML integration example
  - [ ] EUR-USD vs Bond Pearson correlation example

Testing:
  - [ ] Unit tests (80%+ coverage)
  - [ ] Load tests
  - [ ] New performance benchmarks

Cleanup:
  - [ ] Builder cleanup
  - [ ] Remove CSV data layer
  - [ ] Update all documentation
  - [ ] Create migration guide
  - [ ] Final bug fix sweep

Rest
  - [ ] Take a day off