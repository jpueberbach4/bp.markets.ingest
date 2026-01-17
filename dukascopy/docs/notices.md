<u>MT4 is decoded.</u>

## **Notice: Endpoint issues**

Allright, i have analyzed this. The endpoint is not down, only very recent historical downloads have been disabled. 

```sh
https://jetta.dukascopy.com/v1/candles/minute/BRENT.CMD-USD/BID/2026/1/16 <- not work
https://jetta.dukascopy.com/v1/candles/minute/BRENT.CMD-USD/BID/2026/1/15 <- works
https://jetta.dukascopy.com/v1/candles/minute/BRENT.CMD-USD/BID/2026/1/14 <- works

https://jetta.dukascopy.com/v1/candles/minute/EUR-USD/BID/2026/1/16 <- not work
https://jetta.dukascopy.com/v1/candles/minute/EUR-USD/BID/2026/1/15 <- works
https://jetta.dukascopy.com/v1/candles/minute/EUR-USD/BID/2026/1/14 <- works
```

This means that the recent tail cannot be downloaded. Aka, the "liveness" of this project is not possible anymore.

I will provide a fix for this project so that you can use the pipeline but with a lag of two days. There are solutions to restoring liveness but i cannot share these solutions in here because the message is, i think, clear.

There will be a new setting in the download section soon. For historical data this still can be used. Check back for an update soon. 

I would be willing to pay for this "liveness" tail, so i am going to reach out.

## Write-up

I have started with writing up everything i have learned so far in a document [performance.md](performance.md). This project was able to get institutional performance on just a laptop. The project excelled in getting data aligned right. The forementioned document will cover everything, from performance tricks up until market-data specific difficulties. Basically the what, the why and the how of this project. It will be an educational read including in-depth technical howto's.

I will keep you guys posted. Lets see what happens. It is too early to draw any conclusions.

**Note:** Development continues as planned. Data-api is now ready to make "buffered-charts". Updates soon.
