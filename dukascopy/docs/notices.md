Market research- and analysis tool, feature-engineering, but you can do so much more with it, if you are a bit "handy".

New/Updated documentation:

[Adjustments](adjustments.md)
[Templates](templates.md)
[Code examples](../config/plugins/indicators/)

It is now possible to only rebuild specific symbols and its aliasses:

`./rebuild-full.sh --symbol BRENT.CMD-USD --symbol AAPL.US-USD`

**Note:** Make sure that any adjusted sets are always prefixed with SYMBOL eg `BRENT.CMD-USD-RR`.

For rebuilding backadjusted sets you need to specify its origin (source) symbol.

A rebuild of one symbol with 2 aliasses takes about 25 seconds, depending on your hardware. Most of the time goes to scanning what is missing but I will optimize this in the future.

