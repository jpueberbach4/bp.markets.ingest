## **Tests**

- Major Forex. Excellent.
- Major Crosses. Good.
- Dollar index, Volatility index. Good.
- Energy: Brent, WTI, Diesel, GAS. Great.
- Metals: XAU slightly off but (very) usable, Copper is way off (still need to check why, likely data)
- Indices: US indices. Excellent. DAX. Good. NL. Good. Nikkie. Excellent. Still working on the others.
- Bonds: BUND, USNOTE. Good. Gilt not checked (yet).
- A weird edge-case: NZD-USD (Weekly unusable). Daily. Fine.

What was checked? 5m for major forex. Weekly and daily, sometimes 1h and sometimes 15m. Need to build
automation to perform accuracy tests (maybe later).

```sh
Example (why sometimes prices are bit different):

5 Minute aggregation we have performed, output:

2025.12.03,01:00:00,23737.699,23738.899,23733.655,23733.655,0.00195
2025.12.03,01:05:00,23733.955,23735.177,23730.766,23733.155,0.00132

You see in the MT4 chart that 01:00:00/5m has a close price of .955.
In our data is .955 the opening price of 01:05:00 candle.

The following 1m data is what we get from Dukascopy:

time, open, high, low, close, volume
2025.12.03,01:00:00,23737.699,23738.899,23735.599,23737.599,0.000795    -
2025.12.03,01:01:00,23736.988,23736.988,23734.855,23735.299,0.000375     |
2025.12.03,01:02:00,23734.888,23737.277,23734.855,23735.488,0.000315     | 01:00:00
2025.12.03,01:03:00,23735.177,23736.099,23734.877,23735.455,0.00015      |
2025.12.03,01:04:00,23735.788,23736.399,23733.655,23733.655,0.000315    -
2025.12.03,01:05:00,**23733.955**,23734.299,23730.766,23733.155,0.00039 -
2025.12.03,01:06:00,23733.655,23734.399,23733.655,23733.955,0.000225     |
2025.12.03,01:07:00,23733.699,23734.866,23731.955,23731.955,0.000195     | 01:05:00
2025.12.03,01:08:00,23732.399,23735.177,23732.399,23733.988,0.000255     |
2025.12.03,01:09:00,23733.688,23734.288,23732.566,23733.155,0.000255    -

Based on this data, the aggregation is 100% correct. Data is not EXACTLY
the same as in MT4. But very very close. I have seen this boundary-
price issue multiple times during my checks. 
```

![MT4](images/examplepricediff.png)