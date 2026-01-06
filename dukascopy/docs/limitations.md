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
- MIN-MAX date-range API
- Stock split support

**P3 (Nice-to-have):**
- Performance improvements
- Track a live-backadjusted 1m base-including resampling- in a seperate directory (configurable)

**P4 (Architectural):**
- General QA improvements
- IO Layer abstraction \
  By abstracting the IO layer someone, or me, could potentially switch to a binary format, eliminating the 80% consumption because of CSV. I will provide for it, we will see later what to do with it. Scheduled right after replay and the custom-shifting in transform. DuckDB has a read_binary method. Did a quick calculation: estimated speedup: 20-30x. 60-80% storage reduction. So that would mean ~10 million candles per second on commodity hardware (theoretically). That's laughable fast. Initially i didnt want to do this, because the C++ variant already handles it. But its also intriguing to know how far we can push with Python.
- Librarization

This is still in an MVP state. Although working very well. It's an MVP.
