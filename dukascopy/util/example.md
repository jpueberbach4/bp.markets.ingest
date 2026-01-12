# Internal temporary scratchpad

## Symbol discovery example

```sh
discovery = DataDiscovery(config)
available = discovery.scan()

resolver = SelectionResolver(available)
tasks, pairs = resolver.resolve(["EUR-USD:panama/1h,15m", "BTC-USD/1m:skiplast"])
```

TODO: add support for SYM/TF:any:skiplast[ema(20),ema(50),sma(20)]:panama,TF2[ema(100)]