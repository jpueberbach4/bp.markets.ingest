# Alerting

This allows you to set rules for alerting based on indicator values for a specific asset and timeframe.

## Configuration

Example configuration

```yaml
# Top-level configuration block named "EUR"
# This likely represents a strategy or schedule related to EUR (Euro)
EUR:

  # Days of week when the strategy is allowed to run
  # 0–6 typically represent Sunday–Saturday (depending on implementation)
  weekdays: [0,1,2,3,4,5,6]  # Run every day of the week

  # Time of day when the process should execute (HH:MM:SS format)
  # Use * as a wildcard. Eg run every 30 minutes, runat: *:30:00
  run-at: 00:00:00  # Run at midnight (left out = runs at every cron execution time)

  # Start date from which this configuration becomes active
  # Format: 'YYYY-MM-DD HH:MM:SS'
  from_date: '2000-01-01'  # Active starting January 1, 2000

  # End date when this configuration stops being active
  to_date: '3000-05-14'  # Active until May 14, 3000

  # Actions to perform when rules/conditions are satisfied
  actions:

    # Email notification configuration
    email:
      type: gmail  # Email provider type (Gmail SMTP assumed)
      address: destination_account@outlook.com  # Recipient email address
      subject: EUR-USD signal reached  # Subject line of the notification email
      username: mygmail@gmail.com  # Gmail account used to send the email
      password: <see below>  # Password or app-specific password for authentication

    # Webhook notification configuration
    webhook:
      type: webhook  # Indicates this action triggers a webhook
      method: POST  # HTTP method used for the request
      uri: http://localhost:8000/logme  # Endpoint that will receive the webhook call

  # Trading or signal rules
  rules:

  # First rule definition (named rule-1)
  - rule-1:

      # Financial instrument symbol being monitored
      symbol: EUR-USD  # Euro vs US Dollar currency pair

      # Timeframe for market data
      timeframe: 1d  # 1-day candles

      # Indicators used in this rule
      indicators:
      - example-ml-pt_model-best-gen95-f1-0.8235.pt_1  # Machine learning model output indicator
      - rsi_14  # 14-period RSI (Relative Strength Index)

      # Conditions that must be satisfied to trigger actions
      conditions:

      # Condition 1: ML model score threshold
      - gt_threshold:
          column: example-ml-pt_model-best-gen95-f1-0.8235.pt_1__score  # Column containing model score
          operator: '>='  # Greater than or equal comparison
          value: 0.23  # Threshold value

      # Condition 2: RSI filter condition
      - rsi_14:
          column: rsi_14  # RSI indicator column
          operator: '<='  # Less than or equal comparison
          value: 60  # RSI must be 60 or below
```

What This Configuration Does (Summary)

- Runs daily at midnight

- Active between 2000 and 3000

- Monitors EUR-USD on 1-day timeframe

Uses:

- A machine learning model score

- RSI(14) indicator

Triggers actions when:

- Model score ≥ 0.23

- RSI ≤ 60

Sends:

- An email notification

- A POST webhook request

## Cron

```sh
* * * * * cd /repos/bp.markets.ingest/dukascopy && ./run-alerts.sh
```

Executes the alerts every minute. However, when specified with run-at, it will only execute when run-at time is reached.

Note: You must make sure that you have the latest version of the data with `./run.sh`.

## Webhook

The above example does a POST request to the specified URL with the following payload:

```json
{'job': 'EUR', 'rule': 'rule-1', 'symbol': 'EUR-USD', 'time': '2026-03-03T16:30:00.017353', 'data': {'symbol': 'EUR-USD', 'timeframe': '1d', 'time_ms': 1772496000000, 'open': 1.16863, 'high': 1.17067, 'low': 1.153, 'close': 1.15489, 'volume': 146343.34, 'rsi_14': 29.223113503666028, 'example-ml-pt_model-best-gen95-f1-0.8235.pt_1__score': 0.006308595649898052, 'example-ml-pt_model-best-gen95-f1-0.8235.pt_1__signal': 0.0}}
```

## Gmail

How to get your Gmail App Password

Before you run this, Google has one security requirement:

Go to your Google Account settings -> Security.

Make sure 2-Step Verification is turned ON.

In the search bar at the top of settings, type "App Passwords".

Create a new App Password (call it "MilkyWay Alerts").

Google will give you a 16-letter code (e.g., abcd efgh ijkl mnop).

```yaml
actions:
    gmail:
      type: gmail
      address: email@outlook.com  # The destination inbox
      subject: EUR-USD signal reached
      username: your_trading_bot@gmail.com # The sender Gmail account
      password: abcdefghijklmnop           # The 16-letter Google App Password
      smtp_server: smtp.gmail.com
      smtp_port: 587
```
