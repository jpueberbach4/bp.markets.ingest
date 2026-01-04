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
- MT4 flag on HTTP API
- MIN-MAX date-range API

**P3 (Nice-to-have):**
- Performance improvements
- Track a life-backadjusted 1m base-including resampling- in a seperate directory (configurable)

**P4 (Architectural):**
- General QA improvements
- IO Layer abstraction
- Librarization

This is still in an MVP state. Although working very well. It's an MVP.
