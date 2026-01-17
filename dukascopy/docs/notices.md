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

Could be a dataset rebuild on Dukascopy's end. With Martin Luther King Jr day up etc, it gives a window to perform rebuilds. Maintenance. Everything points to this atm. 

## Notice: support for cache-only rebuilds - 2025-01-17

If the download endpoint is unavailable but you have a cache folder and want to modify timeframes and rebuild using those new timeframes, this is now supported. Before running any rebuild scripts, set `orchestrator.disable_downloads` to 1 in `config.user.yaml`.

Important is that your cache folder doesnt have any gaps. If you use an originally constructed cache-folder made by this application, this shouldnt be an existing issue. 

## Notice: buffered interface is now supported - 2025-01-17

I have updated the interface to not keep everything in memory when browsing history-this smooths the UX. It keeps a record of maximum 5000 bars. This is optimized for a laptop 1680x1050. If you have a "wider-screen" you might wanna set the bufferLimit higher in `config.user/dukascopy/http-docs/index.html` (you might need to copy over the new file). Just CTRL+F 5000 and change it to a value that matches your setup.

Still no news on the 503 status. Still same. Their main historical downloads on their own website are also down. IP's user-agents, etc etc etc. All doesnt matter. All same behavior. So still thinking its a technical issue. No reasons to assume its anything else than that. Have a great weekend. 