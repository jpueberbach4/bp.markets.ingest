Market research- and analysis tool, feature-engineering, but you can do so much more with it, if you are a bit "handy".

## Interface

A few improvements have been applied to the interface to improve developer UX a bit. It is now possible to see what an indicator does by hovering over it on the indicator selectbox. Plus, i have added an `Copy API` button to quickly translate what you see on screen into an internal API call. So you can select your features and when complete, directly translate it to an API call. Also you can copy the current symbol quickly to clipboard by clicking on the "symbol" label, just above the symbol selector. This speedsup correlation studies or configuring indicators where you need to input a benchmark symbol-eg pearson.

You need to copy over the `config/dukascopy/http-docs` to your `config.user/dukascopy/http-docs` directory if you want these latest additions.

Example `Copi API` output:

```python
get_data('AAPL.US-USD', '1h', after_ms=1767362400000, limit=1000, order="asc", \
  indicators=["aroon_14","bbands_20_2.0","feature-mad_20_close_sma","feature-nprice_14_close_log", \
    "feature-natr_14_0","feature-vzscore_20_log"], options={**options, "return_polars": True})
```

## Various

New/Updated documentation:

[Adjustments](adjustments.md)
[Templates](templates.md)
[Code examples](../config/plugins/indicators/)

It is now possible to only rebuild specific symbols and its aliasses:

`./rebuild-full.sh --symbol BRENT.CMD-USD --symbol AAPL.US-USD`

Also, if dealing with illiquid assets that need regular "backfill" maintenance, the `rebuild-weekly.sh` now follows same syntax:

`./rebuild-weekly.sh --symbol ETH-USD`

**Note:** Make sure that any adjusted sets are always prefixed with SYMBOL eg `BRENT.CMD-USD-RR`.

For rebuilding backadjusted sets you need to specify its origin (source) symbol.

A rebuild of one symbol with 2 aliasses takes about 25 seconds, depending on your hardware. Most of the time goes to scanning what is missing but I will optimize this in the future.

PS. You can also use this when you have just added a new symbol `./rebuild-full.sh --symbol NEWSYMBOL`.

