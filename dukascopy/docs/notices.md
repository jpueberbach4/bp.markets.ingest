**19 new indicators**

19 new indicators were added. These were "quick-wins".

- **Fast Indicators**: Most use pure Polars vectorization
- **Recursive Indicators**: McGinley, Kalman, SuperTrend use Python loops
- **Heavy Indicators**: Volume/Market Profile use O(n²) histograms

I will have another quality pass on them soon.

**Performance fixes**

Performance fixes have been applied. Update entails:

- Hybrid Polars/Pandas indicator engine
- Native Polars dataframe support from get_data API
- All system indicators have been converted
- Performance +12.5x on 1 million with 55 indicators. Polars only indicators. With return_polars=True ~520ms.
- Performance +8-10x on 1 million with 55 indicators. Mix of high perf hybrids. Without return_polars=True ~730ms.
- Cleaning up here and there.

Profiling showed that >90 percent of time is now going to Polars high-perf rust engine.

I think we have now maxed out what is possible for this stack. There was one more performance update added. Batched execution of Polars expressions (to prevent graph explosion on very wide column data) plus we keep the original fp64 precision intact (no rounding). Rounding is now up to the caller's discretion. Some may need 4 decimals, others 8, fixed rounding at 6 inside the engine was a bad idea anyhow.

I tried the most crazy configurations you can think of and profiled them all. I can't find anything more to tune. This should be the solid performance-base to build the rest on-top. I calculated that it's achieving over 4GB/s in memory bandwidth. That's really impressive for a laptop ryzen 7 nvme combo.

Have a great day.

Current Laptop: ~4.7 GB/s (Impressive).

Ryzen 9 9950X: ~14 GB/s (AVX-512 is the game changer, testing with this setup soon).

Threadripper: ~25 GB/s (Unlocks "Wide" datasets with 10k+ columns).

**Next**

Splitting up ETL to make more modular-more kubernetes friendly, retaking performance there-and adding a high-speed comm-layer. Back at it on wednesday/thursday.

**Status: feeds have returned to operational**

Feeds are back online. No further actions required.

Update: I’ve been in contact with Dukascopy, and they’ve confirmed that the technical hiccups were on their side—they’ve since been fixed. Carry on was the message i read from it.


