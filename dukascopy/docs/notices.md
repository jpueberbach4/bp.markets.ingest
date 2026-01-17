<u>MT4 is decoded.</u>

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

What's next?

I will reach out to Dukascopy, eventually. I would be willing to pay for this feed, in case its not a technical issue. This tool is very cool :)

**Note:** General advice is to stop your crontab trying to execute the downloads until we know exactly whatsup.

## Write-up

I have started with writing up everything i have learned so far in a document [performance.md](performance.md). This project was able to get institutional performance on just a laptop. The project excelled in getting data aligned right. The forementioned document will cover everything, from performance tricks up until market-data specific difficulties. Basically the what, the why and the how of this project. It will be an educational read including in-depth technical howto's.

I will keep you guys posted. Lets see what happens. It is too early to draw any conclusions.

**Note:** Development continues as planned. Data-api is now ready to make "buffered-charts". Updates soon.

**Note:** It could also be: Martin Luther King Jr. Day is up. A major market holiday. Could be regular maintenance. We just dont know atm.


## Notice: support for cache-only rebuilds - 2025-01-17

If the download endpoint is unavailable but you have a cache folder and want to modify timeframes and rebuild using those new timeframes, this is now supported. Before running any rebuild scripts, set `orchestrator.disable_downloads` to 1 in `config.user.yaml`.

Important is that your cache folder doesnt have any gaps. If you use an originally constructed cache-folder made by this application, this shouldnt be an existing issue. 