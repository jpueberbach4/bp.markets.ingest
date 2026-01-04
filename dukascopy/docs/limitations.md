## Limitations

At present, the tool has no known limitations relative to the MT4 platform. I’ve conducted a pretty thorough review, but it’s possible some issues were missed. If you notice anything that should be fixed, please report it via the repository’s Discussions.

Generally speaking, this platform emulates MT4 behavior pretty excellent.

See [Tests](tests.md)

## Open issues / To do list

- Support MT4 flag on HTTP API for "best MT4 EA integration experience"
- Support for getting a MIN-MAX date-range for a symbol on HTTP API
- Performance 1m charts-not bad but can be improved (a lot)
- Custom shifting in transform to support the ASX 2020 anomaly [See here](forensics/ASX.MD).
- Custom shifting in transform to support the DST-switch lag on leap-years.
- Replay functionality
- Beyond compare configuration checks on commodities

This is still in an MVP state. Although working very well. It's an MVP.

- General QA: wrapping builder components in classes
- General QA: wrapping http-service components in classes
- General QA: abstraction of IO layer for resample
- General QA: "librarization" of code

But these things will be done after all bugfixes and after the primary functionalities are done.

