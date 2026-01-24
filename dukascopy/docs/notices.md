<u>MT4 is decoded.</u>

What's next?

- Final round of public development
- Stabilization
- Private and public version
- Replay/Market simulation
- Relaunch

### Notice: clean-version is in the making

I am currently working on the clean-version. This version has undergone another major refactor. It now supports an internal API and performance was pushed even a little bit more. The price-only API has now latency of about 3-5ms(1m, random 2020 date, 1000 records). With 3 indicators-ema,sma,macd-it now pushes around 10ms. That is core-api call. Without the JSON response. Wall time. I will finish this off ASAP and launch it pretty soon. Max 2 weekends away.

Price-only API pushes now ~1.8 million bars per second. 10.000 in ~6ms. Without serialization. This is the max for Python.

### Bonus ML Example: Bottom Detection with Random Forest

this works not oke. building new one
