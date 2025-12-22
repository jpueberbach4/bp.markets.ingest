## Limitations

While the tool is becoming pretty excellent, it is worth noting that there are (still) some limitations. Not many AFAICS.

### Volumes - **Unresolved - will not solve at this time (cannot)**

In MT4, volume on forex charts usually shows tick volume (number of price changes), not actual traded shares/contracts, whereas Dukascopy JSON data for 1m bars (often called delta files) provides a more direct, real volume count (or tick count tied to actual transactions), often reflecting executed trades or ticks per period, giving better market depth insights than generic MT4's simple tick count, but both differ from stock market true volume.

I am testing with a fixed multiply factor for indices though. Here the factor seems to be constant.

### Session from-to support - **Solved, merge support is in for SGD, available in main** 

We have implemented the from_date, to_date for sessions. Using these date-times you can determine between
what timestamps a session is valid/active. 

**Fix details:** Small postprocesssing step when ```timeframe.post``` is defined. See SGD config file for the "bugs-bunny" example.

There are still small candles issues on "candle policy change rollover". Very minor. Moved to longer term todo list.

### Session windows - indices, forex with breaks - **solved, implemented, available in main**

Example: AUS.IDX-AUD (index). The Aussie index has 2 trading sessions (for futures and derivatives). 

- Day Session: 9:50 AM - 4:30 PM (AEST) **
- Overnight (After-Hours) Session: 5:10 PM - 7:00 AM the next morning (AEST) **
- There is a short break between sessions (4:30 PM - 5:10 PM).

In MT4 we will see the candles aligning to HH:50 for the first (day) session and to HH:10 for the after-hours (overnight) session.

We have now support for these kind of "custom" trading windows. 

### YAML configuration is becoming huge - **solved, implemented, available in main**

Given the number of “abnormalities” we need to support, the YAML file is at risk of becoming very large. I plan to add support for an include pattern so the configuration can be split into separate files by section, override, and similar concerns.

We have now support for an  ```includes``` subkey. Any glob file-patterns listed within this key are now included.   

This will help organize the configuration a lot better.