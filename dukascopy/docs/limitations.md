## Limitations

While the tool is becoming pretty excellent, it is worth noting that there are (still) some limitations. Not many AFAICS.

### Volumes - **Unresolved**

Looking into volumes, if there is consistency with the 0.0012 factor across assets. Worst case scenario we need to give a case-example on how to set a good multiplier for an asset. Best case scenario if it's a fixed factor across assets.

SGD.IDX:

| Time | Tool Volume | MT4 Volume | Ratio (MT4 / Tool) |
| :--- | :--- | :--- | :--- |
| **15:51** | 3,778,831 | 4,534 | 0.0012 |
| **19:51** | 1,459,212 | 1,751 | 0.0012 |
| **02:30** | 1,448,412 | 1,738 | 0.0012 |

- **Mean Ratio**: 0.0012

CHI.IDX:

| Time   | Tool Volume  | MT4 Volume | Ratio (MT4 / Tool) |
|--------|-------------------|------------|-----------------------|
| 15:00  | 169,418           | 5,841      | 0.03448               |
| 19:00  | 110,345           | 3,805      | 0.03448               |
| 03:00  | 671,582           | 23,155     | 0.03448               |
| 07:00  | 398,924           | 13,755     | 0.03448               |
| 11:00  | 50,895            | 1,755      | 0.03448               |
| 15:00  | 126,933           | 4,377      | 0.03448               |
| 19:00  | 37,294            | 1,290      | 0.03458               |
| 03:00  | 553,958           | 19,106     | 0.03449               |

- **Mean Ratio**: 0.3448

EUR-USD:

| Time   | Tool Volume | MT4 Volume | Ratio (MT4/Tool) |
|--------|-------------|------------|------------------|
| 04:00  | 7,642.01    | 4,234      | 0.5541           |
| 08:00  | 17,266.85   | 10,837     | 0.6276           |
| 12:00  | 13,704.22   | 8,912      | 0.6503           |
| 16:00  | 27,784.49   | 18,086     | 0.6511           |
| 20:00  | 16,946.03   | 10,865     | 0.6411           |
| 00:00  | 10,288.75   | 5,235      | 0.5089           |
| 04:00  | 10,414.61   | 5,379      | 0.5165           |
| 08:00  | 16,692.09   | 10,132     | 0.6068           |
| 12:00  | 14,813.06   | 9,216      | 0.6221           |
| 16:00  | 33,271.46   | 19,918     | 0.5986           |
| 20:00  | 9,519.38    | 6,107      | 0.6414           |
| 00:00  | 6,932.95    | 5,574      | 0.8041           |
| 04:00  | 6,196.31    | 4,338      | 0.7001           |
| 08:00  | 18,736.42   | 11,699     | 0.6243           |
| 12:00  | 30,120.25   | 19,340     | 0.6421           |
| 16:00  | 36,730.19   | 23,473     | 0.6390           |
| 20:00  | 15,298.15   | 10,165     | 0.6645           |
| 00:00  | 8,260.00    | 4,241      | 0.5134           |
| 04:00  | 13,785.69   | 6,374      | 0.4624           |
| 08:00  | 23,807.60   | 14,571     | 0.6120           |
| 12:00  | 24,457.11   | 14,798     | 0.6050           |
| 16:00  | 30,316.21   | 18,280     | 0.6030           |
| 20:00  | 10,126.04   | 6,463      | 0.6383           |
| 00:00  | 4,708.64    | 3,643      | 0.7738           |
| 04:00  | 8,131.29    | 5,105      | 0.6277           |
| 08:00  | 17,460.27   | 10,785     | 0.6178           |
| 12:00  | 27,097.88   | 18,176     | 0.6707           |
| 16:00  | 35,294.62   | 22,238     | 0.6301           |
| 20:00  | 11,357.70   | 6,373      | 0.5611           |
| 00:00  | 7,933.24    | 5,270      | 0.6643           |
| 04:00  | 7,078.67    | 4,886      | 0.6903           |
| 08:00  | 19,723.26   | 12,522     | 0.6349           |
| 12:00  | 20,566.96   | 12,504     | 0.6080           |
| 16:00  | 23,767.36   | 14,470     | 0.6088           |
| 20:00  | 10,076.38   | 6,790      | 0.6739           |
| 00:00  | 11,584.13   | 8,595      | 0.7420           |
| 04:00  | 7,395.25    | 4,495      | 0.6078           |

- **Mean Ratio**: 0.627
- **Median Ratio**: 0.627
- **Standard Deviation**: 0.065
- **Range**: 0.4624 to 0.8041
- **Most Common Range**: 0.60–0.65

BRENT:

| Time   | Tool Volume  | MT4 Volume | Ratio (MT4/Tool) |
|--------|-------------------|------------|---------------------|
| 03:00  | 570,428           | 3,099      | 0.005433            |
| 07:00  | 732,689           | 4,026      | 0.005496            |
| 11:00  | 1,504,632         | 6,247      | 0.004152            |
| 15:00  | 2,207,555         | 10,608     | 0.004806            |
| 19:00  | 775,388           | 4,715      | 0.006080            |
| 23:00  | 7,228,602         | 810        | 0.000112            |
| 03:00  | 728,103           | 3,430      | 0.004711            |
| 07:00  | 490,500           | 2,796      | 0.005700            |
| 11:00  | 806,622           | 3,931      | 0.004873            |
| 15:00  | 1,545,423         | 8,073      | 0.005224            |
| 19:00  | 747,351           | 4,235      | 0.005666            |
| 23:00  | 2,259,702         | 257        | 0.000114            |
| 03:00  | 429,912           | 1,637      | 0.003808            |
| 07:00  | 589,676           | 3,101      | 0.005259            |
| 11:00  | 833,237           | 4,477      | 0.005373            |
| 15:00  | 1,169,422         | 7,179      | 0.006139            |
| 19:00  | 736,465           | 3,754      | 0.005097            |

**Normal Trading Hours** (excluding 23:00 outliers):
- **Mean Ratio**: 0.005245
- **Median Ratio**: 0.005259
- **Range**: 0.003808 to 0.006139
- **Standard Deviation**: 0.000615

Conclusions:

- Indices: Stable factor. Easy.
- Forex: Dynamic factor. Need to use a median ratio.
- Commodities: Dynamic factor. Need to use a median ratio.

We cannot get it 100% exact for forex and commodities. Indices, we are near exact (note: limited sampling results). Multiplication factor per symbol needs to get supported. This will become feature-014. Needs to get implemented in the transform stage (the base 1m aggregate needs to change. so rebuild-full will be needed when this is done). I am debating if i am letting the transform-step look into the resample-symbols configuration. Seperation of concerns i would like to retain. Need to brain on it.

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