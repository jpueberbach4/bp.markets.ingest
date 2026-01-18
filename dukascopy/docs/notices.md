<u>MT4 is decoded.</u>

What's next?

- Replay/Market simulation
- Optionally reaching out if problems persist longer than expected
- Write-up

## **Notice: Endpoint issues - 503**

I changed code and tried a few things. These are the things i considered

- User-agent blockage: Not the case
  Similar results with regular browser headers
- AWS endpoint issue in Amsterdam (my nearest Dukascopy CDN): Not the case
  Tried VPN services and Google Shell. No difference.
- Historical tail disable (prevent trading bots)
  Seems also not the case.

What's up?

A "Error from Cloudfront". Could basically mean anything. Because of the inconsistent behavior my best guess is technical issues.

What's likely up?

Technical issues.

Charts are down too: https://www.dukascopy.com/swiss/english/marketwatch/charts/

## Notice: been playing around with custom indicators

You can really write neat stuff using custom indicators. Positive divergence (bullish) example-with doji detection.

![Example](../images/reversal.png)
![Example2](../images/reversal2.png)

Currently there are 2 issues which makes custom indicator building a bit tedious:

- you need to restart the webservice
- you need to reload the page, reselect the symbol, timeframe, indicator

I will make changes for that. It's not handy the way it is now. Will make it like this:

- indicator change is detected automatically and refreshed in the service
- pressing update view will update with new output
- refreshing page will remember (last) settings - using browser localstorage (for now)

Rapid prototyping should be possible. The above helps with that.

I will build these things first and then really start with replay.

## Notice: support for cache-only rebuilds - 2025-01-17

If the download endpoint is unavailable but you have a cache folder and want to modify timeframes and rebuild using those new timeframes, this is now supported. Before running any rebuild scripts, set `orchestrator.disable_downloads` to 1 in `config.user.yaml`.

Important is that your cache folder doesnt have any gaps. If you use an originally constructed cache-folder made by this application, this shouldnt be an existing issue. 

## Notice: buffered interface is now supported - 2025-01-17

I have updated the interface to not keep everything in memory when browsing history-this smooths the UX. It keeps a record of maximum 5000 bars. This is optimized for a laptop 1680x1050. If you have a "wider-screen" you might wanna set the bufferLimit higher in `config.user/dukascopy/http-docs/index.html` (you might need to copy over the new file). Just CTRL+F 5000 and change it to a value that matches your setup.
