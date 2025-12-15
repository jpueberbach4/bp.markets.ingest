## Troubleshooting

### What to Do When Pipeline Fails

1. **Check the error message**: "ABORT! Critical error in Transform"
2. **Investigate the root cause**: Check logs, data files
3. **Fix the issue**: Corrupted file? Network issue?
4. **Restart pipeline**: It will resume from last good state

Example recovery:
```bash
# Pipeline fails with "JSON parse error"
rm cache/2024/03/EURUSD_20240315.json  # Remove corrupted file
./run.sh  # Restart - will redownload & continue
```

### Stale Locks

If pipeline was interrupted (laptop sleep, SIGKILL) and you get "Another instance is already running", remove stale locks. This is a very unlikely event.

```bash
rm -rf data/locks/*.lck
```

### Rebuild from scratch?

Full rebuild is needed when you change the symbol-list or when you change the configuration of the transform layer.

```bash
./rebuild-full.sh
```

When you have applied changes to the resample step only:

```sh
./rebuild-weekly.sh
```

### Performance Issues
- **Slow first run?** Normal - processing 20 years of data takes time
- **Slow incremental?** Check if NVMe/SSD. HDDs will be 10-50x slower
- **High CPU?** Reduce `NUM_PROCESSES` in scripts
- **Out of memory?** Reduce `BATCH_SIZE` in resample.py (default: 500K)

### Alignment, candles "don't exactly match your broker"

This pipeline is optimized and pre-configured for Dukascopy Bank's data feed and MT4 platform, offering guaranteed alignment. While the code is open and can be adapted, the smoothest experience and most reliable results are achieved by using the tool with its intended data source. We see this as a complementary service that adds significant value to the high-quality data Dukascopy has generously provided for over 20 years.

```sh
cp config.dukascopy-mt4.yaml config.user.yaml
```

Consider: → [Become a client of Dukascopy](https://live-login.dukascopy.com/rto3/).

### Downloads appear slower after updating to the latest version

This slowdown is caused by a newly introduced rate_limit_rps flag in config.yaml. If you use a custom config.user.yaml, this flag may not be set in the downloads section. In that case, it falls back to the default value of 0.5, which is intentionally conservative and results in slow download speeds. You can safely adjust this value, but keep it reasonable. For an initial full sync, expect to wait a few hours.

To estimate an appropriate rate_limit_rps, you can use the following formulas:

```python
(number_of_symbols * 365 * 20) / (cpu_cores * rate_limit_rps) = num_seconds_to_download

OR -simplified

rate_limit_rps = (number_of_symbols * 73 / 36) / (cpu_cores * hours)
```

**Example:** You want to run the full initial sync overnight, giving you about 8 hours. You have 25 symbols configured and a 16-core machine.

```python
rate_limit_rps = (25 * 73 / 36) / (16 * 8) = 50.69 / 128 = 0.39 (requests per second =~ 6 (0.39 * 16 cores))
```

After initial sync, you can up the value to 1. Rate limits were introduced due to the project’s growing popularity.
