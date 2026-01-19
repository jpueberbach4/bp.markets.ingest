<u>MT4 is decoded.</u>

What's next?

- Replay/Market simulation
- Write-up


## **Notice:** Interface (bug-)fixes - 2025-01-19

Over the weekend, I updated the HTML chart interface to use a buffered approach for “candle memory.” While this worked fine on my laptop, it likely didn’t scale well on desktop setups with much larger screens. The default bufferLimit of 5000 appears to have been too low, forcing users to manually edit index.html and adjust the value to match their setup.

I’ve now implemented a dynamic bufferLimit, which should resolve this issue. For testing, I initialized the bufferLimit to 10, and it seems to be working as expected. I’m primarily a full-stack developer, but JavaScript—especially frontend work—is not my strongest area, as I’m more accustomed to the strictness of backend development.

Additionally, when the tail of the chart is in view, the update logic should now correctly display new candles. I’m still testing this, but so far it looks okay.

Copy over the new `config/dukascopy/http-docs/index.html` to your `config.user/dukascopy/http-docs/index.html`.W


## **Notice: Endpoint issues - 503** - 2025-01-18

What's up?

A "Error from Cloudfront".  Because of the inconsistent behavior my best guess is technical issues.

**Update:** Issues have been resolved.

Monday is MLK (Martin Luther King Jr) day, being a major market holiday.

## Notice: hot-reload of CUSTOM indicators is now done - 2025-01-18

Hot-reload of custom indicators has now been implemented. No more webservice restarts needed if you ADD/CHANGE an indicator. Goal of these changes is to support "rapid prototyping", ease the developer experience. 

**Important:** Do not use `_`-underscore-in indicator file-names. If you need to seperate, use a `-`-dash- or a `.`-dot.

**Update:** The chart-web-UI has been updated to reload indicators on "Update view". So if you add/modify an indicator, press "Update view" to reload its settings/newly added indicators. `index.html` has changed once more, copy over the file manually to `config.user`. Note that it only works for CUSTOM indicators. The system ones will not be refreshed without a webservice restart. You shouldnt change them anyways.

**Note:** Sometimes with "dragging" the chart, it flips a bit. Use pagedown/pageup/end keys. Still needs some polishing. But is of later concern. I am not so great at frontend development. It's not so "strict" as backend. The asynchronous stuff with JSONP. Brrr. 

## Notice: been playing around with custom indicators - 2025-01-18

You can really write neat stuff using custom indicators. Positive divergence (bullish) example-with doji detection.

![Example](../images/reversal.png)
![Example4](../images/reversal4.png)

Honestly, its not flawless yet. But for a first attempt? Pretty good.

![Example5](../images/reversal5.png)
![Example6](../images/reversal6.png)

This is 100 percent without lookahead bias. 

Python for custom indicators? Pure gold.

## Notice: support for cache-only rebuilds - 2025-01-17

If the download endpoint is unavailable but you have a cache folder and want to modify timeframes and rebuild using those new timeframes, this is now supported. Before running any rebuild scripts, set `orchestrator.disable_downloads` to 1 in `config.user.yaml`.

Important is that your cache folder doesnt have any gaps. If you use an originally constructed cache-folder made by this application, this shouldnt be an existing issue. 

## Notice: buffered interface is now supported - 2025-01-17

I have updated the interface to not keep everything in memory when browsing history-this smooths the UX. It keeps a record of maximum 5000 bars. This is optimized for a laptop 1680x1050. If you have a "wider-screen" you might wanna set the bufferLimit higher in `config.user/dukascopy/http-docs/index.html` (you might need to copy over the new file). Just CTRL+F 5000 and change it to a value that matches your setup.
