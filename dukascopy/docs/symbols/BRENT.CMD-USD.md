# BRENT.CMD-USD

Investigating the following:
```sh
OKTOBER(4H): 

2025.10.24,19:00:00,66.305,66.325,65.758,65.802,4.675582	<! WEEKEND ENTRY
NO 2025.10.24,23:00 CANDLE                                  <! MISSING 
2025.10.26,23:00:00,66.373,66.468,66.203,66.203,4.670148	<! SUNDAY CANDLE?
2025.10.27,03:00:00,66.208,66.235,65.918,66.19,0.512396		<! MARKET OPEN

NOVEMBER(4H):

2025.11.07,19:00:00,63.66,63.795,63.205,63.662,7.033396
2025.11.07,23:00:00,63.655,63.722,63.617,63.642,6.804948	<! WEEKEND ENTRY
NO 2025.11.09,23:00 CANDLE					                <! MISSING SUNDAY CANDLE
2025.11.10,03:00:00,63.787,64.115,63.787,64.042,1.714851	<! MARKET OPEN
...
2025.11.21,23:00:00,62.43,62.468,62.398,62.432,1.746446		<! WEEKEND ENTRY
NO 2025.11.23,23:00 CANDLE					                <! MISSING SUNDAY CANDLE
2025.11.24,03:00:00,62.317,62.625,62.295,62.555,0.262244	<! MARKET OPEN

DECEMBER(4H):

NO MORE SUNDAY 23:00 CANDLES.

The Daylight Saving Time (DST) change in November 2025 occurred on:

🗓️ Date: Sunday, November 2, 2025

DST change. That's a bug i need to solve. Explains why the candles did line up
when switching between GMT+3 and GMT+2. Hence all these commits. So we need to
shift based on what date it is. I need to build logic for that.
```


