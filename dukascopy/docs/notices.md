<u>MT4 is decoded.</u>

What's next?

- Final round of public development
- Stabilization
- Private and public version
- Replay/Market simulation
- Relaunch

## Beta version 0.6.7

A major refactor/overhaul was carried out (again) to support the internal API. The beta is stable and has been in use for several days with no alarming issues observed; it should be effectively bug-free.

The primary advantage of this beta is support for interdata querying from custom indicators, enabling the creation of correlated indicators. Additionally, excessive sorting and indexing have been removed, resulting in further performance improvements across the API.

The price-only API now delivers 10,000 one-minute EUR/USD records in 6 ms (excluding serialization), compared to 10–11 ms previously—an additional performance gain of roughly 40%

```sh
git fetch -p
git checkout origin beta/0.6.7
```

As always with beta's: use at your own risk. There were no changes to the ETL ingestion. Should be backward-compatible/non-breaking.

Expected release date: weekend of 31st January.




