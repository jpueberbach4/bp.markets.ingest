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

Price only API pushes about 18.5 million, 64-bytes, 1m records per second. After warmup. On a laptop with NVMe.

PS: there is a dirty_loadtest.py in examples if you want to confirm. Adjust bootstrap paths and symbol before run.

**Note**: important one. Performance measured while using the internal, [bootstrapped](external.md), get_data API.

Batch-size: 500k is my optimal batchsize for highest throughput for the price-only API. 

```sh
192: 500000 records, time-passed: 13.257286977022886 ms (price-only API)
193: 500000 records, time-passed: 13.019719044677913 ms (price-only API)
194: 500000 records, time-passed: 14.547841041348875 ms (price-only API)
195: 500000 records, time-passed: 14.952547964639962 ms (price-only API)
196: 500000 records, time-passed: 13.805115013383329 ms (price-only API)
197: 500000 records, time-passed: 12.885914067737758 ms (price-only API)
198: 500000 records, time-passed: 14.367218012921512 ms (price-only API)
```

Best run 0.0129s. 500000/0.0128s =~ 39 million records/sec * 64 bytes =~ 2.5GB/s (warmed up) 

**Next**

Few days of rest/other things, then splitting up ETL to make more modular-more kubernetes friendly, retaking performance there-and adding a high-speed comm-layer. Back at it on wednesday/thursday.

**Status: feeds have returned to operational**

Feeds are back online. No further actions required.

Update: I’ve been in contact with Dukascopy, and they’ve confirmed that the technical hiccups were on their side—they’ve since been fixed. Carry on was the message i read from it.


