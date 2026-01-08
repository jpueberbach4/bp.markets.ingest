## Limitations

At present, the tool has no known limitations relative to the MT4 platform. I’ve conducted a pretty thorough review, but it’s possible some issues were missed. If you notice anything that should be fixed, please report it via the repository’s Discussions.

Generally speaking, this platform emulates MT4 behavior pretty excellent.

See [Tests](tests.md)

## Open issues / To do list

**P1 (Critical):**
- Custom shifting for ASX 2020 anomaly
- Custom shifting for one-week-leap-year DST lag (affects Nov 2020,2024,2028,etc)
- Replay functionality

**P2 (Important):**
- Redesign of HTTP API for version 1.1
- MIN-MAX date-range API
- Stock split support

**P3 (Nice-to-have):**
- Further Performance improvements (partitioning of data)
- Track a live-backadjusted 1m base-including resampling- in a seperate directory (configurable)

**P4 (Architectural):**
- Add some LRU caches here and there for processes that are continuously running
- General QA improvements
- Librarization

This is still in an MVP state. Although working very well. It's an MVP.


