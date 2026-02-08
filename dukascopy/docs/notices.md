**Fix for the open-candle problem - NEEDS BTC-USD as HEARTBEAT symbol**

We have a temporary solution for the "open-candle" problem. Eg mark the open-candle in the output `is_open:1` or `is_open:0`. However, this requires you to configure the symbol `BTC-USD` and have it synced up. The `BTC-USD` symbol acts as the heartbeat of the market. 

And indicator `status` was added to the internal system indicators. You can query it in your webinterface or subquery it using `get_data` by passing `status` as an indicator.

This is a temporary but ROBUST solution when you can update at least `ONCE EVERY TWO HOURS`. So for live connections this works where update-time is < 2 hours. Eg your crontab setting is once-every-two-hours. You get the point.

Another robustness update is coming for the "cabin in the woods but no internet"-problem.

You can checkout the indicator [here](../util/plugins/indicators/status.py).

**Another performance update**

This one hits your indicators. You can now optionally accept a polars Dataframe inside of your plugin. You need to set `meta.polars_input` to 1. The calling function then passes in a polars dataframe. You can then either return a pandas dataframe or a polars dataframe. Generic advice is to prevent conversions as much as possible. So polars input has the preference. 

Gain? For 1000 records on a complex recursive indicator: 51ms to 19ms. 60000 records from 100ms to 37ms. See the [indicators](indicators.md) doc.

So my statement that it couldnt be pushed further was wrong-at least for "calculate"-indicators.

Recursive calls got a lot cheaper.

The HTTP-API is still on Pandas. It will be sped up too by switching it to return_polars=True. So the HTTP Wall time includes a conversion-overhead from polars to pandas. This is why it might feel that the latest performance fix actually does nothing, on the web-interface.

The truth is (internal optimized get_data call), with complex indicator: 1000000 records, time-passed: 92.94088200840633 ms + 1 indicators (which subqueries both H4 and D1 frame RSI). I have added the HTTP-API fix to the todo list. This evening off. Something for tomorrow's sprint.

**Next**

Hardening, quality. Then. Splitting up ETL to make more modular-more kubernetes friendly, retaking performance there-and adding a high-speed comm-layer.

**Status: feeds have returned to operational**

Feeds are back online. No further actions required.

Update: I’ve been in contact with Dukascopy, and they’ve confirmed that the technical hiccups were on their side—they’ve since been fixed. Carry on was the message i read from it.


**List of ta-lib custom indicators**

```sh
Registered plugin config.user/plugins/indicators/talib-ad.py succesfully.
Registered plugin config.user/plugins/indicators/talib-add.py succesfully.
Registered plugin config.user/plugins/indicators/talib-adosc.py succesfully.
Registered plugin config.user/plugins/indicators/talib-adxr.py succesfully.
Registered plugin config.user/plugins/indicators/talib-apo.py succesfully.
Registered plugin config.user/plugins/indicators/talib-aroonosc.py succesfully.
Registered plugin config.user/plugins/indicators/talib-atan.py succesfully.
Registered plugin config.user/plugins/indicators/talib-avgprice.py succesfully.
Registered plugin config.user/plugins/indicators/talib-beta.py succesfully.
Registered plugin config.user/plugins/indicators/talib-bop.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdl2crows.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdl3blackcrows.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdl3inside.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdl3linestrike.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdl3outside.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdl3starsinsouth.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdl3whitesoldiers.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdlabandonedbaby.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdladvanceblock.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdlbelthold.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdlbreakaway.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdlclosingmarubozu.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdlconcealbabyswall.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdlcounterattack.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdldarkcloudcover.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdldoji.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdldojistar.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdldragonflydoji.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdlengulfing.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdleveningdojistar.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdleveningstar.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdlgapsidesidewhite.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdlgravestonedoji.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdlhammer.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdlhangingman.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdlharami.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdlharamicross.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdlhighwave.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdlhikkake.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdlhikkakemod.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdlhomingpigeon.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdlidentical3crows.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdlinneck.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdlinvertedhammer.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdlkicking.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdlkickingbylength.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdlladderbottom.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdllongleggeddoji.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdllongline.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdlmarubozu.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdlmatchinglow.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdlmathold.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdlmorningdojistar.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdlmorningstar.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdlonneck.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdlpiercing.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdlrickshawman.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdlrisefall3methods.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdlseparatinglines.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdlshootingstar.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdlshortline.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdlspinningtop.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdlstalledpattern.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdlsticksandwich.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdltakuri.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdltasukigap.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdlthrusting.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdltristar.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdlunique3river.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdlupsidegap2crows.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cdlxsidegap3methods.py succesfully.
Registered plugin config.user/plugins/indicators/talib-ceil.py succesfully.
Registered plugin config.user/plugins/indicators/talib-correl.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cos.py succesfully.
Registered plugin config.user/plugins/indicators/talib-cosh.py succesfully.
Registered plugin config.user/plugins/indicators/talib-dema.py succesfully.
Registered plugin config.user/plugins/indicators/talib-div.py succesfully.
Registered plugin config.user/plugins/indicators/talib-dx.py succesfully.
Registered plugin config.user/plugins/indicators/talib-exp.py succesfully.
Registered plugin config.user/plugins/indicators/talib-floor.py succesfully.
Registered plugin config.user/plugins/indicators/talib-ht_dcperiod.py succesfully.
Registered plugin config.user/plugins/indicators/talib-ht_dcphase.py succesfully.
Registered plugin config.user/plugins/indicators/talib-ht_phasor.py succesfully.
Registered plugin config.user/plugins/indicators/talib-ht_sine.py succesfully.
Registered plugin config.user/plugins/indicators/talib-ht_trendline.py succesfully.
Registered plugin config.user/plugins/indicators/talib-ht_trendmode.py succesfully.
Registered plugin config.user/plugins/indicators/talib-kama.py succesfully.
Registered plugin config.user/plugins/indicators/talib-linearreg.py succesfully.
Registered plugin config.user/plugins/indicators/talib-linearreg_angle.py succesfully.
Registered plugin config.user/plugins/indicators/talib-linearreg_intercept.py succesfully.
Registered plugin config.user/plugins/indicators/talib-linearreg_slope.py succesfully.
Registered plugin config.user/plugins/indicators/talib-ln.py succesfully.
Registered plugin config.user/plugins/indicators/talib-log10.py succesfully.
Registered plugin config.user/plugins/indicators/talib-ma.py succesfully.
Registered plugin config.user/plugins/indicators/talib-macdext.py succesfully.
Registered plugin config.user/plugins/indicators/talib-macdfix.py succesfully.
Registered plugin config.user/plugins/indicators/talib-mama.py succesfully.
Registered plugin config.user/plugins/indicators/talib-mavp.py succesfully.
Registered plugin config.user/plugins/indicators/talib-max.py succesfully.
Registered plugin config.user/plugins/indicators/talib-maxindex.py succesfully.
Registered plugin config.user/plugins/indicators/talib-medprice.py succesfully.
Registered plugin config.user/plugins/indicators/talib-midprice.py succesfully.
Registered plugin config.user/plugins/indicators/talib-min.py succesfully.
Registered plugin config.user/plugins/indicators/talib-minindex.py succesfully.
Registered plugin config.user/plugins/indicators/talib-minmax.py succesfully.
Registered plugin config.user/plugins/indicators/talib-minmaxindex.py succesfully.
Registered plugin config.user/plugins/indicators/talib-minus_di.py succesfully.
Registered plugin config.user/plugins/indicators/talib-minus_dm.py succesfully.
Registered plugin config.user/plugins/indicators/talib-mom.py succesfully.
Registered plugin config.user/plugins/indicators/talib-mult.py succesfully.
Registered plugin config.user/plugins/indicators/talib-natr.py succesfully.
Registered plugin config.user/plugins/indicators/talib-plus_di.py succesfully.
Registered plugin config.user/plugins/indicators/talib-plus_dm.py succesfully.
Registered plugin config.user/plugins/indicators/talib-ppo.py succesfully.
Registered plugin config.user/plugins/indicators/talib-rocp.py succesfully.
Registered plugin config.user/plugins/indicators/talib-rocr.py succesfully.
Registered plugin config.user/plugins/indicators/talib-rocr100.py succesfully.
Registered plugin config.user/plugins/indicators/talib-sar.py succesfully.
Registered plugin config.user/plugins/indicators/talib-sarext.py succesfully.
Registered plugin config.user/plugins/indicators/talib-sin.py succesfully.
Registered plugin config.user/plugins/indicators/talib-sinh.py succesfully.
Registered plugin config.user/plugins/indicators/talib-sqrt.py succesfully.
Registered plugin config.user/plugins/indicators/talib-stddev.py succesfully.
Registered plugin config.user/plugins/indicators/talib-stochf.py succesfully.
Registered plugin config.user/plugins/indicators/talib-stochrsi.py succesfully.
Registered plugin config.user/plugins/indicators/talib-sub.py succesfully.
Registered plugin config.user/plugins/indicators/talib-sum.py succesfully.
Registered plugin config.user/plugins/indicators/talib-t3.py succesfully.
Registered plugin config.user/plugins/indicators/talib-tan.py succesfully.
Registered plugin config.user/plugins/indicators/talib-tanh.py succesfully.
Registered plugin config.user/plugins/indicators/talib-tema.py succesfully.
Registered plugin config.user/plugins/indicators/talib-trange.py succesfully.
Registered plugin config.user/plugins/indicators/talib-trima.py succesfully.
Registered plugin config.user/plugins/indicators/talib-trix.py succesfully.
Registered plugin config.user/plugins/indicators/talib-tsf.py succesfully.
Registered plugin config.user/plugins/indicators/talib-typprice.py succesfully.
Registered plugin config.user/plugins/indicators/talib-var.py succesfully.
Registered plugin config.user/plugins/indicators/talib-wclprice.py succesfully.
Registered plugin config.user/plugins/indicators/talib-wma.py succesfully.
```







