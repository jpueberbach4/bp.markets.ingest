It was a busy weekend so today-monday-is a day off. Chilling.

## **BUG!**

Today, 2026-02-09T1730+0100, i found a bug while i was working with CSV data for trading. I use this stuff myself too, meaning automatically that deeper integration tests are being performed. I found out that mixing pandas indicators with polars dataframe indicators, somehow got broken. I have fixed this.

You will need to update. Now, a decent mix has been tested on 1 million records:

indicators = ['is-open', 'rsi-1h4h1d_14','aroon_14','atrp_14','atr_14','ema_9','ema_18','ema_30','macd_12_26_9']

While this is fixed, I will need to do automated performance tests on the connectors. Another unit-test will come for that. The aroon indicator is very slow. The execution time of the above list is 1.2s. When I remove aroon, this drops to 120-140ms. 

So yes, there is a need for automated performance testing of indicators. There may be more slow ones which i didnt catch before since not all, like aroon, wereincluded in previous load-tests.

Note: when you copied the example for the 3x RSI: you will need to update it. See templates.md/indicators.md.

Update: Yeah we have some winners:

```sh
[SETUP] Data generation complete. Memory: 1.63 MB
----------------------------------------------------------------------------
STATUS   | INDICATOR                 |  TIME (ms) | TYPE            | SOURCE
----------------------------------------------------------------------------
✅ OK    | status2                   |       0.72 | Polars DF       | config.user
✅ OK    | talib-ad                  |       0.47 | Pandas DF       | config.user
✅ OK    | talib-add                 |       0.18 | Pandas DF       | config.user
✅ OK    | talib-adosc               |       0.41 | Pandas DF       | config.user
✅ OK    | talib-adxr                |       0.33 | Pandas DF       | config.user
✅ OK    | talib-apo                 |       0.19 | Pandas DF       | config.user
✅ OK    | talib-aroonosc            |       0.26 | Pandas DF       | config.user
✅ OK    | talib-atan                |       0.30 | Pandas DF       | config.user
✅ OK    | talib-avgprice            |       0.18 | Pandas DF       | config.user
✅ OK    | talib-beta                |       0.23 | Pandas DF       | config.user
✅ OK    | talib-bop                 |       0.18 | Pandas DF       | config.user
✅ OK    | talib-cdl2crows           |       0.26 | Pandas DF       | config.user
✅ OK    | talib-cdl3blackcrows      |       0.25 | Pandas DF       | config.user
✅ OK    | talib-cdl3inside          |       0.28 | Pandas DF       | config.user
✅ OK    | talib-cdl3linestrike      |       0.27 | Pandas DF       | config.user
✅ OK    | talib-cdl3outside         |       0.23 | Pandas DF       | config.user
✅ OK    | talib-cdl3starsinsouth    |       0.31 | Pandas DF       | config.user
✅ OK    | talib-cdl3whitesoldiers   |       0.32 | Pandas DF       | config.user
✅ OK    | talib-cdlabandonedbaby    |       0.30 | Pandas DF       | config.user
✅ OK    | talib-cdladvanceblock     |       0.42 | Pandas DF       | config.user
✅ OK    | talib-cdlbelthold         |       0.28 | Pandas DF       | config.user
✅ OK    | talib-cdlbreakaway        |       0.38 | Pandas DF       | config.user
✅ OK    | talib-cdlclosingmarubozu  |       0.42 | Pandas DF       | config.user
✅ OK    | talib-cdlconcealbabyswall |       0.42 | Pandas DF       | config.user
✅ OK    | talib-cdlcounterattack    |       0.41 | Pandas DF       | config.user
✅ OK    | talib-cdldarkcloudcover   |       0.43 | Pandas DF       | config.user
✅ OK    | talib-cdldoji             |       0.19 | Pandas DF       | config.user
✅ OK    | talib-cdldojistar         |       0.35 | Pandas DF       | config.user
✅ OK    | talib-cdldragonflydoji    |       0.28 | Pandas DF       | config.user
✅ OK    | talib-cdlengulfing        |       1.00 | Pandas DF       | config.user
✅ OK    | talib-cdleveningdojistar  |       0.31 | Pandas DF       | config.user
✅ OK    | talib-cdleveningstar      |       0.30 | Pandas DF       | config.user
✅ OK    | talib-cdlgapsidesidewhite |       0.30 | Pandas DF       | config.user
✅ OK    | talib-cdlgravestonedoji   |       0.26 | Pandas DF       | config.user
✅ OK    | talib-cdlhammer           |       0.30 | Pandas DF       | config.user
✅ OK    | talib-cdlhangingman       |       0.30 | Pandas DF       | config.user
✅ OK    | talib-cdlharami           |       0.35 | Pandas DF       | config.user
✅ OK    | talib-cdlharamicross      |       0.29 | Pandas DF       | config.user
✅ OK    | talib-cdlhighwave         |       0.28 | Pandas DF       | config.user
✅ OK    | talib-cdlhikkake          |       0.21 | Pandas DF       | config.user
✅ OK    | talib-cdlhikkakemod       |       0.25 | Pandas DF       | config.user
✅ OK    | talib-cdlhomingpigeon     |       0.33 | Pandas DF       | config.user
✅ OK    | talib-cdlidentical3crows  |       0.34 | Pandas DF       | config.user
✅ OK    | talib-cdlinneck           |       0.27 | Pandas DF       | config.user
✅ OK    | talib-cdlinvertedhammer   |       0.29 | Pandas DF       | config.user
✅ OK    | talib-cdlkicking          |       0.32 | Pandas DF       | config.user
✅ OK    | talib-cdlkickingbylength  |       0.31 | Pandas DF       | config.user
✅ OK    | talib-cdlladderbottom     |       0.31 | Pandas DF       | config.user
✅ OK    | talib-cdllongleggeddoji   |       0.27 | Pandas DF       | config.user
✅ OK    | talib-cdllongline         |       0.43 | Pandas DF       | config.user
✅ OK    | talib-cdlmarubozu         |       0.29 | Pandas DF       | config.user
✅ OK    | talib-cdlmatchinglow      |       0.32 | Pandas DF       | config.user
✅ OK    | talib-cdlmathold          |       0.33 | Pandas DF       | config.user
✅ OK    | talib-cdlmorningdojistar  |       1.13 | Pandas DF       | config.user
✅ OK    | talib-cdlmorningstar      |       0.54 | Pandas DF       | config.user
✅ OK    | talib-cdlonneck           |       0.37 | Pandas DF       | config.user
✅ OK    | talib-cdlpiercing         |       0.41 | Pandas DF       | config.user
✅ OK    | talib-cdlrickshawman      |       0.42 | Pandas DF       | config.user
✅ OK    | talib-cdlrisefall3methods |       0.49 | Pandas DF       | config.user
✅ OK    | talib-cdlseparatinglines  |       0.36 | Pandas DF       | config.user
✅ OK    | talib-cdlshootingstar     |       0.38 | Pandas DF       | config.user
✅ OK    | talib-cdlshortline        |       0.38 | Pandas DF       | config.user
✅ OK    | talib-cdlspinningtop      |       0.31 | Pandas DF       | config.user
✅ OK    | talib-cdlstalledpattern   |       0.36 | Pandas DF       | config.user
✅ OK    | talib-cdlsticksandwich    |       0.31 | Pandas DF       | config.user
✅ OK    | talib-cdltakuri           |       0.29 | Pandas DF       | config.user
✅ OK    | talib-cdltasukigap        |       0.33 | Pandas DF       | config.user
✅ OK    | talib-cdlthrusting        |       0.28 | Pandas DF       | config.user
✅ OK    | talib-cdltristar          |       0.46 | Pandas DF       | config.user
✅ OK    | talib-cdlunique3river     |       0.40 | Pandas DF       | config.user
✅ OK    | talib-cdlupsidegap2crows  |       0.31 | Pandas DF       | config.user
✅ OK    | talib-cdlxsidegap3methods |       0.31 | Pandas DF       | config.user
✅ OK    | talib-ceil                |       0.24 | Pandas DF       | config.user
✅ OK    | talib-correl              |       0.33 | Pandas DF       | config.user
✅ OK    | talib-cos                 |       0.36 | Pandas DF       | config.user
✅ OK    | talib-cosh                |       0.26 | Pandas DF       | config.user
✅ OK    | talib-dema                |       0.31 | Pandas DF       | config.user
✅ OK    | talib-div                 |       0.19 | Pandas DF       | config.user
✅ OK    | talib-dx                  |       0.27 | Pandas DF       | config.user
✅ OK    | talib-exp                 |       0.24 | Pandas DF       | config.user
✅ OK    | talib-floor               |       0.17 | Pandas DF       | config.user
✅ OK    | talib-ht_dcperiod         |       0.73 | Pandas DF       | config.user
✅ OK    | talib-ht_dcphase          |       4.92 | Pandas DF       | config.user
✅ OK    | talib-ht_phasor           |       0.73 | Pandas DF       | config.user
✅ OK    | talib-ht_sine             |       5.17 | Pandas DF       | config.user
✅ OK    | talib-ht_trendline        |       0.77 | Pandas DF       | config.user
✅ OK    | talib-ht_trendmode        |       5.84 | Pandas DF       | config.user
✅ OK    | talib-kama                |       0.28 | Pandas DF       | config.user
✅ OK    | talib-linearreg           |       0.47 | Pandas DF       | config.user
✅ OK    | talib-linearreg_angle     |       0.43 | Pandas DF       | config.user
✅ OK    | talib-linearreg_intercept |       0.30 | Pandas DF       | config.user
✅ OK    | talib-linearreg_slope     |       0.27 | Pandas DF       | config.user
✅ OK    | talib-ln                  |       0.20 | Pandas DF       | config.user
✅ OK    | talib-log10               |       0.23 | Pandas DF       | config.user
✅ OK    | talib-ma                  |       0.20 | Pandas DF       | config.user
✅ OK    | talib-macdext             |       0.34 | Pandas DF       | config.user
✅ OK    | talib-macdfix             |       0.46 | Pandas DF       | config.user
✅ OK    | talib-mama                |       0.19 | Pandas DF       | config.user
✅ OK    | talib-mavp                |       0.18 | Pandas DF       | config.user
✅ OK    | talib-max                 |       0.21 | Pandas DF       | config.user
✅ OK    | talib-maxindex            |       0.21 | Pandas DF       | config.user
✅ OK    | talib-medprice            |       0.20 | Pandas DF       | config.user
✅ OK    | talib-midprice            |       0.37 | Pandas DF       | config.user
✅ OK    | talib-min                 |       0.23 | Pandas DF       | config.user
✅ OK    | talib-minindex            |       0.22 | Pandas DF       | config.user
✅ OK    | talib-minmax              |       0.28 | Pandas DF       | config.user
✅ OK    | talib-minmaxindex         |       0.27 | Pandas DF       | config.user
✅ OK    | talib-minus_di            |       0.27 | Pandas DF       | config.user
✅ OK    | talib-minus_dm            |       0.25 | Pandas DF       | config.user
✅ OK    | talib-mom                 |       0.16 | Pandas DF       | config.user
✅ OK    | talib-mult                |       0.16 | Pandas DF       | config.user
✅ OK    | talib-natr                |       0.23 | Pandas DF       | config.user
✅ OK    | talib-plus_di             |       0.24 | Pandas DF       | config.user
✅ OK    | talib-plus_dm             |       0.25 | Pandas DF       | config.user
✅ OK    | talib-ppo                 |       0.18 | Pandas DF       | config.user
✅ OK    | talib-rocp                |       0.21 | Pandas DF       | config.user
✅ OK    | talib-rocr                |       0.17 | Pandas DF       | config.user
✅ OK    | talib-rocr100             |       0.28 | Pandas DF       | config.user
✅ OK    | talib-sar                 |       0.24 | Pandas DF       | config.user
✅ OK    | talib-sarext              |       0.23 | Pandas DF       | config.user
✅ OK    | talib-sin                 |       0.25 | Pandas DF       | config.user
✅ OK    | talib-sinh                |       0.21 | Pandas DF       | config.user
✅ OK    | talib-sqrt                |       0.18 | Pandas DF       | config.user
✅ OK    | talib-stochf              |       0.24 | Pandas DF       | config.user
✅ OK    | talib-stochrsi            |       0.39 | Pandas DF       | config.user
✅ OK    | talib-sub                 |       0.17 | Pandas DF       | config.user
✅ OK    | talib-sum                 |       0.18 | Pandas DF       | config.user
✅ OK    | talib-t3                  |       0.18 | Pandas DF       | config.user
✅ OK    | talib-tan                 |       0.46 | Pandas DF       | config.user
✅ OK    | talib-tanh                |       0.23 | Pandas DF       | config.user
✅ OK    | talib-tema                |       0.27 | Pandas DF       | config.user
✅ OK    | talib-trange              |       0.17 | Pandas DF       | config.user
✅ OK    | talib-trima               |       0.18 | Pandas DF       | config.user
✅ OK    | talib-trix                |       0.24 | Pandas DF       | config.user
✅ OK    | talib-tsf                 |       0.36 | Pandas DF       | config.user
✅ OK    | talib-typprice            |       0.29 | Pandas DF       | config.user
✅ OK    | talib-var                 |       0.20 | Pandas DF       | config.user
✅ OK    | talib-wclprice            |       0.17 | Pandas DF       | config.user
✅ OK    | test-sma-rsi-auto         |       1.46 | Pandas DF       | config.user
✅ OK    | test-sma-rsi              |       1.17 | Polars Expr     | config.user
✅ OK    | adl                       |       1.35 | Polars Expr     | util
✅ OK    | adx                       |       8.19 | Polars Expr     | util
⚠️ SLOW  | aroon                     |      34.93 | Polars Expr     | util
✅ OK    | atr                       |       1.84 | Polars Expr     | util
✅ OK    | atrp                      |       1.38 | Polars Expr     | util
✅ OK    | autocorr                  |       2.25 | Polars Expr     | util
✅ OK    | bbands-width              |       1.45 | Polars Expr     | util
✅ OK    | bbands                    |       0.75 | Polars Expr     | util
✅ OK    | camarilla-pivots          |       2.81 | Polars Expr     | util
⚠️ SLOW  | cci                       |    2440.07 | Polars Expr     | util
✅ OK    | chaikin                   |       2.91 | Polars Expr     | util
✅ OK    | chande-kroll-stop         |       1.93 | Polars Expr     | util
✅ OK    | choppiness                |       1.26 | Polars Expr     | util
✅ OK    | cmo                       |       0.93 | Polars Expr     | util
✅ OK    | coppock-curve             |       2.29 | Polars Expr     | util
✅ OK    | donchian-width            |       1.24 | Polars Expr     | util
✅ OK    | donchian                  |       0.96 | Polars Expr     | util
✅ OK    | elderray                  |       0.82 | Polars Expr     | util
✅ OK    | ema                       |       0.22 | Polars Expr     | util
✅ OK    | eom                       |       0.93 | Polars Expr     | util
✅ OK    | fibonacci                 |       6.10 | Polars Expr     | util
⚠️ SLOW  | fractaldimension          |    1747.42 | Polars Expr     | util
✅ OK    | hma                       |       8.18 | Polars Expr     | util
⚠️ SLOW  | hurst                     |    7530.55 | Polars Expr     | util
✅ OK    | ichimoku                  |       1.87 | Polars Expr     | util
✅ OK    | is-open                   |       0.32 | Polars DF       | util
✅ OK    | kalman                    |       6.34 | Polars Expr     | util
✅ OK    | kaufman-er                |       0.93 | Polars Expr     | util
✅ OK    | kdj                       |       6.99 | Polars Expr     | util
✅ OK    | keltner                   |       2.26 | Polars Expr     | util
⚠️ SLOW  | linregchannel             |      28.95 | Polars Expr     | util
✅ OK    | macd                      |       4.47 | Polars Expr     | util
⚠️ SLOW  | marketprofile             |     432.43 | Pandas DF       | util
✅ OK    | mcginley                  |       4.74 | Polars Expr     | util
✅ OK    | mfi                       |       4.05 | Polars Expr     | util
✅ OK    | midpoint                  |       0.59 | Polars Expr     | util
✅ OK    | obv                       |       0.87 | Polars Expr     | util
✅ OK    | pivot                     |       3.96 | Polars Expr     | util
✅ OK    | psar                      |       9.79 | Polars Expr     | util
✅ OK    | psychlevels               |       0.14 | Polars Expr     | util
✅ OK    | roc                       |       1.58 | Polars Expr     | util
✅ OK    | rsi                       |       0.54 | Polars Expr     | util
⚠️ SLOW  | shannonentropy            |    1845.01 | Pandas DF       | util
✅ OK    | sharpe                    |       2.47 | Polars Expr     | util
✅ OK    | sma                       |       0.15 | Polars Expr     | util
✅ OK    | stc                       |       5.49 | Pandas DF       | util
✅ OK    | stddev                    |       0.41 | Polars Expr     | util
✅ OK    | stochastic                |       3.43 | Polars Expr     | util
⚠️ SLOW  | supertrend                |      11.15 | Polars Expr     | util
✅ OK    | uo                        |       3.76 | Polars Expr     | util
✅ OK    | volatility-ratio          |       2.24 | Polars Expr     | util
⚠️ SLOW  | volumeprofile             |     519.26 | Pandas DF       | util
✅ OK    | vqi                       |       0.89 | Polars Expr     | util
⚠️ SLOW  | vwap                      |      13.93 | Polars Expr     | util
✅ OK    | vwma                      |       0.57 | Polars Expr     | util
✅ OK    | williamsr                 |       2.80 | Polars Expr     | util
✅ OK    | zscore                    |       2.48 | Polars Expr     | util
```

I have done one performance optimization pass:

```sh
[SETUP] Generating 10000 rows of OHLCV data for performance testing...
[SETUP] Data generation complete. Memory: 1.75 MB
----------------------------------------------------------------------------
STATUS   | INDICATOR                 |  TIME (ms) | TYPE            | SOURCE
----------------------------------------------------------------------------
✅ OK    | rsi-1h4h1d                |       6.43 | Polars DF       | config.user <!-- the 3x RSI one
✅ OK    | status2                   |       0.75 | Polars DF       | config.user
✅ OK    | talib-ad                  |       0.67 | Pandas DF       | config.user
✅ OK    | talib-add                 |       0.17 | Pandas DF       | config.user
✅ OK    | talib-adosc               |       0.25 | Pandas DF       | config.user
✅ OK    | talib-adxr                |       0.29 | Pandas DF       | config.user
✅ OK    | talib-apo                 |       0.22 | Pandas DF       | config.user
✅ OK    | talib-aroonosc            |       0.35 | Pandas DF       | config.user
✅ OK    | talib-atan                |       0.34 | Pandas DF       | config.user
✅ OK    | talib-avgprice            |       0.23 | Pandas DF       | config.user
✅ OK    | talib-beta                |       0.24 | Pandas DF       | config.user
✅ OK    | talib-bop                 |       0.25 | Pandas DF       | config.user
✅ OK    | talib-cdl2crows           |       0.33 | Pandas DF       | config.user
✅ OK    | talib-cdl3blackcrows      |       0.25 | Pandas DF       | config.user
✅ OK    | talib-cdl3inside          |       0.27 | Pandas DF       | config.user
✅ OK    | talib-cdl3linestrike      |       0.26 | Pandas DF       | config.user
✅ OK    | talib-cdl3outside         |       0.23 | Pandas DF       | config.user
✅ OK    | talib-cdl3starsinsouth    |       0.36 | Pandas DF       | config.user
✅ OK    | talib-cdl3whitesoldiers   |       0.49 | Pandas DF       | config.user
✅ OK    | talib-cdlabandonedbaby    |       0.39 | Pandas DF       | config.user
✅ OK    | talib-cdladvanceblock     |       0.68 | Pandas DF       | config.user
✅ OK    | talib-cdlbelthold         |       0.28 | Pandas DF       | config.user
✅ OK    | talib-cdlbreakaway        |       0.28 | Pandas DF       | config.user
✅ OK    | talib-cdlclosingmarubozu  |       0.33 | Pandas DF       | config.user
✅ OK    | talib-cdlconcealbabyswall |       0.32 | Pandas DF       | config.user
✅ OK    | talib-cdlcounterattack    |       0.39 | Pandas DF       | config.user
✅ OK    | talib-cdldarkcloudcover   |       0.29 | Pandas DF       | config.user
✅ OK    | talib-cdldoji             |       0.25 | Pandas DF       | config.user
✅ OK    | talib-cdldojistar         |       0.28 | Pandas DF       | config.user
✅ OK    | talib-cdldragonflydoji    |       0.92 | Pandas DF       | config.user
✅ OK    | talib-cdlengulfing        |       0.25 | Pandas DF       | config.user
✅ OK    | talib-cdleveningdojistar  |       0.34 | Pandas DF       | config.user
✅ OK    | talib-cdleveningstar      |       0.37 | Pandas DF       | config.user
✅ OK    | talib-cdlgapsidesidewhite |       0.38 | Pandas DF       | config.user
✅ OK    | talib-cdlgravestonedoji   |       0.33 | Pandas DF       | config.user
✅ OK    | talib-cdlhammer           |       0.42 | Pandas DF       | config.user
✅ OK    | talib-cdlhangingman       |       0.38 | Pandas DF       | config.user
✅ OK    | talib-cdlharami           |       0.27 | Pandas DF       | config.user
✅ OK    | talib-cdlharamicross      |       0.28 | Pandas DF       | config.user
✅ OK    | talib-cdlhighwave         |       0.29 | Pandas DF       | config.user
✅ OK    | talib-cdlhikkake          |       0.23 | Pandas DF       | config.user
✅ OK    | talib-cdlhikkakemod       |       0.22 | Pandas DF       | config.user
✅ OK    | talib-cdlhomingpigeon     |       0.26 | Pandas DF       | config.user
✅ OK    | talib-cdlidentical3crows  |       0.32 | Pandas DF       | config.user
✅ OK    | talib-cdlinneck           |       0.27 | Pandas DF       | config.user
✅ OK    | talib-cdlinvertedhammer   |       0.28 | Pandas DF       | config.user
✅ OK    | talib-cdlkicking          |       0.40 | Pandas DF       | config.user
✅ OK    | talib-cdlkickingbylength  |       0.40 | Pandas DF       | config.user
✅ OK    | talib-cdlladderbottom     |       0.29 | Pandas DF       | config.user
✅ OK    | talib-cdllongleggeddoji   |       0.33 | Pandas DF       | config.user
✅ OK    | talib-cdllongline         |       0.36 | Pandas DF       | config.user
✅ OK    | talib-cdlmarubozu         |       0.34 | Pandas DF       | config.user
✅ OK    | talib-cdlmatchinglow      |       0.27 | Pandas DF       | config.user
✅ OK    | talib-cdlmathold          |       1.34 | Pandas DF       | config.user
✅ OK    | talib-cdlmorningdojistar  |       0.33 | Pandas DF       | config.user
✅ OK    | talib-cdlmorningstar      |       0.32 | Pandas DF       | config.user
✅ OK    | talib-cdlonneck           |       0.27 | Pandas DF       | config.user
✅ OK    | talib-cdlpiercing         |       0.32 | Pandas DF       | config.user
✅ OK    | talib-cdlrickshawman      |       0.31 | Pandas DF       | config.user
✅ OK    | talib-cdlrisefall3methods |       0.33 | Pandas DF       | config.user
✅ OK    | talib-cdlseparatinglines  |       0.30 | Pandas DF       | config.user
✅ OK    | talib-cdlshootingstar     |       0.30 | Pandas DF       | config.user
✅ OK    | talib-cdlshortline        |       0.38 | Pandas DF       | config.user
✅ OK    | talib-cdlspinningtop      |       0.53 | Pandas DF       | config.user
✅ OK    | talib-cdlstalledpattern   |       0.49 | Pandas DF       | config.user
✅ OK    | talib-cdlsticksandwich    |       0.29 | Pandas DF       | config.user
✅ OK    | talib-cdltakuri           |       0.38 | Pandas DF       | config.user
✅ OK    | talib-cdltasukigap        |       0.35 | Pandas DF       | config.user
✅ OK    | talib-cdlthrusting        |       0.33 | Pandas DF       | config.user
✅ OK    | talib-cdltristar          |       0.33 | Pandas DF       | config.user
✅ OK    | talib-cdlunique3river     |       0.31 | Pandas DF       | config.user
✅ OK    | talib-cdlupsidegap2crows  |       0.32 | Pandas DF       | config.user
✅ OK    | talib-cdlxsidegap3methods |       0.25 | Pandas DF       | config.user
✅ OK    | talib-ceil                |       0.18 | Pandas DF       | config.user
✅ OK    | talib-correl              |       0.27 | Pandas DF       | config.user
✅ OK    | talib-cos                 |       0.26 | Pandas DF       | config.user
✅ OK    | talib-cosh                |       0.20 | Pandas DF       | config.user
✅ OK    | talib-dema                |       0.21 | Pandas DF       | config.user
✅ OK    | talib-div                 |       0.24 | Pandas DF       | config.user
✅ OK    | talib-dx                  |       0.30 | Pandas DF       | config.user
✅ OK    | talib-exp                 |       0.30 | Pandas DF       | config.user
✅ OK    | talib-floor               |       0.23 | Pandas DF       | config.user
✅ OK    | talib-ht_dcperiod         |       0.68 | Pandas DF       | config.user
✅ OK    | talib-ht_dcphase          |       4.47 | Pandas DF       | config.user
✅ OK    | talib-ht_phasor           |       0.74 | Pandas DF       | config.user
✅ OK    | talib-ht_sine             |       4.94 | Pandas DF       | config.user
✅ OK    | talib-ht_trendline        |       0.88 | Pandas DF       | config.user
✅ OK    | talib-ht_trendmode        |       4.89 | Pandas DF       | config.user
✅ OK    | talib-kama                |       0.19 | Pandas DF       | config.user
✅ OK    | talib-linearreg           |       0.38 | Pandas DF       | config.user
✅ OK    | talib-linearreg_angle     |       0.36 | Pandas DF       | config.user
✅ OK    | talib-linearreg_intercept |       0.27 | Pandas DF       | config.user
✅ OK    | talib-linearreg_slope     |       0.27 | Pandas DF       | config.user
✅ OK    | talib-ln                  |       0.18 | Pandas DF       | config.user
✅ OK    | talib-log10               |       0.21 | Pandas DF       | config.user
✅ OK    | talib-ma                  |       0.25 | Pandas DF       | config.user
✅ OK    | talib-macdext             |       0.47 | Pandas DF       | config.user
✅ OK    | talib-macdfix             |       0.59 | Pandas DF       | config.user
✅ OK    | talib-mama                |       0.26 | Pandas DF       | config.user
✅ OK    | talib-mavp                |       0.23 | Pandas DF       | config.user
✅ OK    | talib-max                 |       0.28 | Pandas DF       | config.user
✅ OK    | talib-maxindex            |       0.25 | Pandas DF       | config.user
✅ OK    | talib-medprice            |       0.21 | Pandas DF       | config.user
✅ OK    | talib-midprice            |       0.32 | Pandas DF       | config.user
✅ OK    | talib-min                 |       0.22 | Pandas DF       | config.user
✅ OK    | talib-minindex            |       0.21 | Pandas DF       | config.user
✅ OK    | talib-minmax              |       0.28 | Pandas DF       | config.user
✅ OK    | talib-minmaxindex         |       0.27 | Pandas DF       | config.user
✅ OK    | talib-minus_di            |       0.25 | Pandas DF       | config.user
✅ OK    | talib-minus_dm            |       0.22 | Pandas DF       | config.user
✅ OK    | talib-mom                 |       0.27 | Pandas DF       | config.user
✅ OK    | talib-mult                |       0.22 | Pandas DF       | config.user
✅ OK    | talib-natr                |       0.31 | Pandas DF       | config.user
✅ OK    | talib-plus_di             |       0.42 | Pandas DF       | config.user
✅ OK    | talib-plus_dm             |       0.29 | Pandas DF       | config.user
✅ OK    | talib-ppo                 |       0.29 | Pandas DF       | config.user
✅ OK    | talib-rocp                |       0.24 | Pandas DF       | config.user
✅ OK    | talib-rocr                |       0.30 | Pandas DF       | config.user
✅ OK    | talib-rocr100             |       0.21 | Pandas DF       | config.user
✅ OK    | talib-sar                 |       0.26 | Pandas DF       | config.user
✅ OK    | talib-sarext              |       0.23 | Pandas DF       | config.user
✅ OK    | talib-sin                 |       0.24 | Pandas DF       | config.user
✅ OK    | talib-sinh                |       0.21 | Pandas DF       | config.user
✅ OK    | talib-sqrt                |       0.21 | Pandas DF       | config.user
✅ OK    | talib-stochf              |       0.29 | Pandas DF       | config.user
✅ OK    | talib-stochrsi            |       0.39 | Pandas DF       | config.user
✅ OK    | talib-sub                 |       0.19 | Pandas DF       | config.user
✅ OK    | talib-sum                 |       0.18 | Pandas DF       | config.user
✅ OK    | talib-t3                  |       0.36 | Pandas DF       | config.user
✅ OK    | talib-tan                 |       0.56 | Pandas DF       | config.user
✅ OK    | talib-tanh                |       0.20 | Pandas DF       | config.user
✅ OK    | talib-tema                |       0.24 | Pandas DF       | config.user
✅ OK    | talib-trange              |       0.17 | Pandas DF       | config.user
✅ OK    | talib-trima               |       0.18 | Pandas DF       | config.user
✅ OK    | talib-trix                |       0.31 | Pandas DF       | config.user
✅ OK    | talib-tsf                 |       0.43 | Pandas DF       | config.user
✅ OK    | talib-typprice            |       0.19 | Pandas DF       | config.user
✅ OK    | talib-var                 |       0.18 | Pandas DF       | config.user
✅ OK    | talib-wclprice            |       0.17 | Pandas DF       | config.user
✅ OK    | test-sma-rsi-auto         |       2.01 | Pandas DF       | config.user
✅ OK    | test-sma-rsi              |       1.53 | Polars Expr     | config.user
✅ OK    | adl                       |       1.41 | Polars Expr     | util
✅ OK    | adx                       |       9.04 | Polars DF       | util
✅ OK    | aroon                     |       3.06 | Polars DF       | util
✅ OK    | atr                       |       1.88 | Polars Expr     | util
✅ OK    | atrp                      |       1.31 | Polars Expr     | util
✅ OK    | autocorr                  |       2.25 | Polars Expr     | util
✅ OK    | bbands-width              |       1.60 | Polars Expr     | util
✅ OK    | bbands                    |       1.55 | Polars Expr     | util
✅ OK    | camarilla-pivots          |       4.36 | Polars Expr     | util
✅ OK    | cci                       |       5.73 | Polars DF       | util
✅ OK    | chaikin                   |       2.76 | Polars Expr     | util
✅ OK    | chande-kroll-stop         |       2.31 | Polars Expr     | util
✅ OK    | choppiness                |       1.09 | Polars Expr     | util
✅ OK    | cmo                       |       0.69 | Polars Expr     | util
✅ OK    | coppock-curve             |       2.06 | Polars Expr     | util
✅ OK    | donchian-width            |       1.14 | Polars Expr     | util
✅ OK    | donchian                  |       1.07 | Polars Expr     | util
✅ OK    | elderray                  |       0.95 | Polars Expr     | util
✅ OK    | ema                       |       0.23 | Polars Expr     | util
✅ OK    | eom                       |       1.23 | Polars Expr     | util
✅ OK    | fibonacci                 |       4.96 | Polars Expr     | util
⚠️ SLOW  | fractaldimension          |      19.95 | Polars DF       | util
✅ OK    | hma                       |       9.22 | Polars Expr     | util
✅ OK    | hurst                     |       7.25 | Polars DF       | util
✅ OK    | ichimoku                  |       2.77 | Polars Expr     | util
✅ OK    | is-open                   |       0.79 | Polars DF       | util
✅ OK    | kalman                    |       6.23 | Polars Expr     | util
✅ OK    | kaufman-er                |       0.91 | Polars Expr     | util
✅ OK    | kdj                       |       7.20 | Polars Expr     | util
✅ OK    | keltner                   |       1.62 | Polars Expr     | util
✅ OK    | linregchannel             |       3.80 | Polars DF       | util
✅ OK    | macd                      |       4.35 | Polars Expr     | util
⚠️ SLOW  | marketprofile             |     423.47 | Polars DF       | util
⚠️ SLOW  | mcginley                  |      17.41 | Polars Expr     | util
✅ OK    | mfi                       |       3.20 | Polars Expr     | util
✅ OK    | midpoint                  |       0.82 | Polars Expr     | util
✅ OK    | obv                       |       8.23 | Polars Expr     | util
✅ OK    | pivot                     |       6.51 | Polars Expr     | util
⚠️ SLOW  | psar                      |      17.08 | Polars DF       | util
✅ OK    | psychlevels               |       0.28 | Polars Expr     | util
✅ OK    | roc                       |       1.48 | Polars Expr     | util
✅ OK    | rsi                       |       0.77 | Polars Expr     | util
⚠️ SLOW  | shannonentropy            |     801.78 | Polars DF       | util
✅ OK    | sharpe                    |       1.02 | Polars Expr     | util
✅ OK    | sma                       |       0.17 | Polars Expr     | util
✅ OK    | stc                       |       3.75 | Pandas DF       | util
✅ OK    | stddev                    |       0.25 | Polars Expr     | util
✅ OK    | stochastic                |       1.97 | Polars Expr     | util
⚠️ SLOW  | supertrend                |      10.09 | Polars Expr     | util
✅ OK    | uo                        |       2.19 | Polars Expr     | util
✅ OK    | volatility-ratio          |       2.19 | Polars Expr     | util
⚠️ SLOW  | volumeprofile             |     533.03 | Pandas DF       | util
✅ OK    | vqi                       |       1.31 | Polars Expr     | util
⚠️ SLOW  | vwap                      |      19.02 | Polars Expr     | util
✅ OK    | vwma                      |       1.83 | Polars Expr     | util
✅ OK    | williamsr                 |       3.66 | Polars Expr     | util
✅ OK    | zscore                    |       3.89 | Polars Expr     | util
```

Marketprofile and volumeprofile cannot be optimized. Will check it once more... but is difficult because of the nature of these two. Shannonentropy was horrible, is better, but still way too high. Others were fixed.

## **Replay mockup is back**

I have re-inserted the "bit scroll-glitchy" replay mockup for demonstration purposes. You can use it to simulate market replay. It can be handy for certain purposes-eg examining custom-indicator-crosses. Its just a mockup but works with all your symbols, timeframes and indicators. I will leave it in. Copy over the `config/dukascopy/http-docs/replay-mockup.html` to your `config.user/dukascopy/http-docs/replay-mockup.html` if you want to "play with it".

After copying `http://localhost:8000/replay-mockup.html`

PS: this is a "chart player or playback", not a real replay. The real one will have partial bar building etc. But that is for later. Core needs to be great first.

## **HTTP-API now Polars-native**

HTTP-API is now polars native. When querying with polars:1 indicators -> blazing. Good update.

## **HTTP-STATUS 400 is now "transient"**

I forgot to mention but this was implemented already a "few" commits back. Status-code 400 is now transient. That means when the ingestion encounters a 400 state, it will retry. This makes ingestion a bit more robust. Play with the number of retries, the backoff factor and the timeout if you are having issues syncing up. Don't overdo it on the rps setting though.

Preliminary conclusion, since 3 weekends in a row: 400 errors? it's maintenance. When you are in-sync and somehow use this for 24/7 trading purposes, monitor your BTC-1m-candles closely (in the weekend). I will provide that `is-stale` counter-part to `is-open` soon.

## **WSL Fast-API issue - `--reload` consumes one core**

I had a go at it but took too much time to solve quickly. Tried watchfiles, watchdog, exclusions, inclusions. Everything. The problem is that, under WSL2, the inotify is broken. So when a file changes, the inotification is not being raised. FastAPI/UVLOOP with `--reload` detects that it is not working and instead goes in a loop mode. This causes the CPU-issue. Since the root has many files (cache, data,..).

**Update:** It is now configurable in the `config.user.yaml`. `http.reload:0` = do not watch files, no cpu-loop under WSL2 (production setting). `http.reload:1` watches files for changes and immediately adds new indicators to the interface (after pressing update view) as you add them (development setting).

Note: changes to existing indicators are detected when `http.reload:0`. 

## **Fix for the open-candle problem - NEEDS BTC-USD as HEARTBEAT symbol**

We have a solution for the "open-candle" problem. Eg mark the open-candle in the output `is-open:1` or `is-open:0`. However, this requires you to configure the symbol `BTC-USD` and have it synced up. The `BTC-USD` symbol acts as the heartbeat of the market. 

Configure the `BTC-USD` symbol as last symbol in your `symbol.user.txt` to ensure maximum reliability.

The indicator `is-open` was added to the internal system indicators. You can query it in your webinterface or subquery it using `get_data` by passing `is-open` as an indicator.

This is a ROBUST solution.

You can checkout the indicator [here](../util/plugins/indicators/is-open.py).

**Update:** This approach works really well, and its simplicity stems from the system's design. The fail-fast principle plays a key role: if even one symbol’s download fails, the process fails immediately—preventing updates for any symbol.

When all downloads succeed, and BTC-USD has new data, it serves as the reference point. If BTC-USD has new data but GBP-USD does not, this indicates that the GBP-USD market is closed.

We can then take the last minute of BTC-USD data and subtract the timespan of the last candle (e.g., 4 hours). If the result is later than the start time of that last candle, the candle is considered closed.

This method is symbol-agnostic and automatically handles market closures, holidays, and similar scenarios

**Update:** The cabin-in-the-woods-without-internet problem is a non-existent problem for `is-open`. We do not use the laptops `time()` anywhere. It only looks at the timestamps of the ingested candles. However, since we need to detect staleness-eg the dataprovider died on a market-we will introduce another indicator: `is-stale`. This indicator can be used to `safeguard` things. Soon.

## **Next**

Hardening, quality. Panama-data sidetrack. Then. Splitting up ETL to make more modular-more kubernetes friendly, retaking performance there-and adding a high-speed comm-layer.

