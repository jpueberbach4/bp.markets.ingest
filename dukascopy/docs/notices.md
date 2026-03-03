# Alerts

**THIS MAY BREAK YOUR SETUP IF YOUR CONFIG IS INVALID. UPDATE WITH CARE. THE ETL IS SAFE. IT USES ITS OWN SCHEMA.JSON FILE. THE API, ML AND ALERTS ARE AFFECTED ONLY**

A "first-version" of alerting is implemented. Its a beta-version and is currently being tested. 

See [here](../ml/alerts/readme.MD) for more information.

You can specify indicators, a timeframe, a symbol and some basic rules. When it alerts, it can post to a webhook or send an email using gmail (or if you have a local smtp server, to localhost).

Its very simplistic but covers the intension pretty well.

I needed automated alerts for models upon completion of daily candles. 

Note: since i have added schema json checking to the main config loader, this could break systems that have invalid config settings. It's a good thing to have the config matched up to the standards.

Test your config by either running `./run-ml.sh` with a universe or `./run-alerts.sh`. The latter checks immediately, even if you dont have a config yet. 

This can also be used for other indicators than models. Basically the whole set is supported.

Example configuration:

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

# ML

You can read all about ML and neuro-evolution soon. I am currently writing up all the knowhow needed to understand this stuff. It is promising but requires A LOT of tuning to be usable (read: reliable). Tune too much and you get overfitted. Looking into that atm. There must be some way to simplify this. Eg scanning data, comeup with a configuration proposal. Or at least minimum automated tweaking of config. It's very timeconsuming to get the models right (for lower TF's).

I will be giving the alerting system a bit of priority. So, documentation and alerting system. After that comes the PNL stuff. And after that additional ML cores (SRNN and TFT).

Meanwhile I have added some of my private indicators. CMF, Trix, MOM and Vortex. More will be added upcoming days.

Wil I be sharing the models themselves? As soon as I have done PNL testing and have tested them on the live edge (have a few running) etc I will share some. Cannot share models for which we dont know if they are profitable yes/no. Firing correctly yes/no on live edge. This needs to be clear first. 

Also some models look regime-dependent. That needs to be out first.

ATM one of the models is signaling for the EUR-USD. So, lets see (personal opinion is that it may drop to 1.1650-ish).

Update: it is already clear that manual intervention is needed and models cannot be trusted blindly. The model said long but i went short :). The committee wil get build. So you will have multiple models voting on the last slice of timeseries. Does the majority, weighted, agree -> send signal. Trying to add the different ML cores asap. Want to know if this approach brings more stability.

There is one potential issue with the committee approach and that is the need for computational power. Instead of one model you will be training three at the same time. I will check if i can shortcut computation here and there by optimization. Especially TFT (Temporal Fusion Transformer) is computationally heavy.

Update: i have done a "long training" of eur-usd. Now the model is quiet on the edge. Question is: will it correctly identify the bottom when it occurs. Lets see. I am doing a bit of other stuff today but this evening i will build the alerting system. I dont want to look all the time if its correct yes or no. It should notify me.

# 🚀 Release Update: Developer UX & Surgical Maintenance

This project is a high-performance market research and analysis tool focused on feature engineering. While optimized for **"mechanical sympathy"** at the hardware level, these latest additions focus on improving the daily workflow for developers and researchers.



