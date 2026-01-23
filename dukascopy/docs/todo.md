## Short term todo list

Initial refactor/preparation stage:
  - [x] Abstracting indicator registry
  - [x] Implementation get_data method (internal API)
  - [x] Minimalization of API 1.1 (no functionality strip)
  - [x] Strip of API 1.0
  - [x] Generic QA passes
  - [x] Initial performance tests. Did we lose, yes/no? Answer: no.

DAG Execution:
  - [ ] Directed Acyclic Graph for indicators
  - [ ] Virtual indicators
  - [ ] Dependency resolution
  - [ ] Real parallel execution

ASX:
  - [ ] Custom timeshifting

DuckDB:
  - [ ] Eliminate completely

Panama:
  - [ ] Panama prevents text-strip, invent solution for binary

Drawing/Visualization:
  - [ ] Split JS to libs (chart.js, drawing.js, ui.js)
  - [ ] Drawing tools (lines, channels, fibs)
  - [ ] Export to PNG/SVG?

API Layer:
  - [ ] Cross-asset queries
  - [ ] Cross-timeframe queries

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