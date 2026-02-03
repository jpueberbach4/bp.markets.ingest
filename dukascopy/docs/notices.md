**Performance fixes**

Performance fixes have been applied. Update entails:

- Hybrid Polars/Pandas indicator engine
- Native Polars dataframe support from get_data API
- All system indicators have been converted
- Performance +12.5x on 1 million with 55 indicators. Polars only indicators. With return_polars=True ~520ms.
- Performance +8-10x on 1 million with 55 indicators. Mix of high perf hybrids. Without return_polars=True ~730ms.
- Cleaning up here and there.

Profiling showed that >90 percent of time is now going to Polars high-perf rust engine.

Price only API pushes about 18.5 million records per second. After warmup. On a laptop with NVMe.

PS: there is a dirty_loadtest.py in examples if you want to confirm. Adjust bootstrap paths and symbol before run.

**Note**: important one. Performance measured while using the internal, [bootstrapped](external.md), get_data API.

**Next**

Few days of rest/other things, then splitting up ETL to make more modular-more kubernetes friendly, retaking performance there-and adding a high-speed comm-layer. Back at it on wednesday/thursday.

**Status: feeds have returned to operational**

Feeds are back online. No further actions required.

Update: I’ve been in contact with Dukascopy, and they’ve confirmed that the technical hiccups were on their side—they’ve since been fixed. Carry on was the message i read from it.


