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

In the unlikely case that the issues are intentional, i will try to work something out with Dukascopy to arrange a paid access for these feeds and this tool. Where users can subscribe. I think it's fair to pay for the infrastructure cost that goes along with delivering this data. For me, now i have played with custom indicators, and have some initial versions of stuff, its a major major gamechanger. Already. And replay isnt even there yet. The tool, ofcourse, will remain in development and free of charge.

This is not monetization of this tool, its making sure it stays around.

Monday is MLK (Martin Luther King Jr) day, being a major market holiday.


## Notice: hot-reload of CUSTOM indicators is now done - 2025-01-18

Hot-reload of custom indicators has now been implemented. No more webservice restarts needed if you ADD/CHANGE an indicator. Now, it still has to get supported in the interfaces. Reloading when you press "update view". Goal of these changes is to support "rapid prototyping", ease the developer experience. 

Note that it only works for CUSTOM indicators. The system ones will not be refreshed without a webservice restart. You shouldnt change them anyways.

**Important:** Do not use `_`-understore-in indicator file-names. If you need to seperate, use a `-`-dash- or a `.`-dot.

## Notice: been playing around with custom indicators - 2025-01-18

You can really write neat stuff using custom indicators. Positive divergence (bullish) example-with doji detection.

![Example](../images/reversal.png)
![Example2](../images/reversal2.png)
![Example3](../images/reversal3.png)
![Example4](../images/reversal4.png)

Honestly, its not flawless yet. But for a first attempt? Pretty good.

![Example5](../images/reversal5.png)
![Example6](../images/reversal6.png)

This is 100 percent without lookahead bias. Imagine this filtering out false-positives and then monitoring all assets on a daily basis. The few signals you might see in these screenshots, when applied to many assets, you would get a signal every so many days. 

I realize myself now, how powerful this actually has become. Python for custom indicators? Pure gold. Moondust.

When feed access is restored, nomatter in what way, and replay is done, the next logical step would be an "alert-system". Thinking out loud: runs periodically. Queries the API. You have business rules setup that looks for combinations of values, in either combined or single feeds, when the conditional rules match fields -> email (or popup with star wars sound, whatever).

## Notice: support for cache-only rebuilds - 2025-01-17

If the download endpoint is unavailable but you have a cache folder and want to modify timeframes and rebuild using those new timeframes, this is now supported. Before running any rebuild scripts, set `orchestrator.disable_downloads` to 1 in `config.user.yaml`.

Important is that your cache folder doesnt have any gaps. If you use an originally constructed cache-folder made by this application, this shouldnt be an existing issue. 

## Notice: buffered interface is now supported - 2025-01-17

I have updated the interface to not keep everything in memory when browsing history-this smooths the UX. It keeps a record of maximum 5000 bars. This is optimized for a laptop 1680x1050. If you have a "wider-screen" you might wanna set the bufferLimit higher in `config.user/dukascopy/http-docs/index.html` (you might need to copy over the new file). Just CTRL+F 5000 and change it to a value that matches your setup.
