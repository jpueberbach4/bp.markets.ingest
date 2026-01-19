<u>MT4 is decoded.</u>

What's next?

- Replay/Market simulation
- Write-up


## **Notice:** Accidently introduced a bug during the 503 issues** - 2025-01-19

Good morning. Because of the 503 issues i introduced a flag, disable_downloads and made changes in run.py. Part of these changes have been reverted because they disabled loading the end-tail-the day of today. Advice is to update and perform a `./rebuild-weekly.sh` to reinitialize the pointers. Sorry about this.

Have a great day

PS: a `./rebuild-weekly.sh` will also make sure that the files of last week are in-check. if you are completely new and didnt do any rebuild yet, use the `./rebuild-full.sh` script. For users that really want to check things out and have EUR-USD, you can run `python3 dump.py`. This checks the last date of the aggregate file-the last date should be now-1 minute. If your `data/temp` directory doesnt have any .bin files, `weekly-rebuild.sh`. Cronjobs can be enabled again.

One more thing. The update view button doesnt refresh the tail. The updated data comes in correctly. So its an interface thingy. I will fix this soon. I have to go on some other business first but when i get back i will fix it. As a temporary solution you can switch the timeframes forth and back. 

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
