## **Notice: Project Transition to Private Development**

This project will be taken offline soon. All future development will continue **privately**.

**Why?**  
This is ultimately about generating real P/L, not about chasing clone statistics or turning into a public maintenance burden.

**What happens next?**

- **Current repo** (this one) → will be archived / made private after migration.
- **New public repo** → a separate, locked, thoroughly tested release containing **only** the stable foundational layer:
  - Dukascopy download → transform → aggregate → resample → binary storage
  - Basic HTTP API for querying OHLCV + simple indicators
  - **No maintenance, no support, no updates** — as-is forever. Think of it as a clean, reliable data bridge you can fork and build on.
- **Private continuation** → everything that actually drives edge:
  - Advanced stuff

**Last public development round (before migration)** includes:
- DAG execution of indicators + virtual indicators
- Drawing tools added to index.html + JS modularization
- Internal API layer for indicators (mmap-based, DataFrame in/out)
- One example cross-asset indicator: Pearson correlation (e.g., bonds vs EUR-USD)
- Unit tests + basic load tests
- Complete removal of CSV support (base data only binary)
- Minor polish / cleanup

**Timeline** → ASAP (target: beginning of February 2026 or sooner).

**Eventual relaunch will happen**

I won't leave people empty-handed — the stable version will still be powerful enough to do serious work. Trust me, the core pipeline works extremely well today.

Thank you to everyone who cloned, tested, starred or gave feedback — the traction has been unreal and very motivating.

— JP