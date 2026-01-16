<u>MT4 is decoded.</u>

## **Notice: We are being throttled

Hi. At first i thought the user-agent was being blocked, but that is not the case. We are severely being throttled. That is actually good news. It means the project is still usable for all users, except with degraded (download-)performance.

If you are in-sync already, you are in luck. You only need to change some settings in your config.user.yaml

Find the download section

```yaml
  timeout: 30                         # Request timeout
  rate_limit_rps: 0.2                   # Protect end-point (number of cores * rps = requests/second)
```

Set the values to the same settings above. This should be able to let you retrieve your data.

I was afraid that this would happen, if you want more speed, you need to be a bit technical. But it is possible. 

>The what, the why and the how: By reducing the load, you are staying below the "Burst" threshold of their WAF (Web Application Firewall). This is a classic "Polite ETL" maneuver that ensures long-term survival of the data feed.

Also, i have started to write up everything i have learned on this project. I think this knowledge should be open. If you are interested in the internals of this project, the why, the what and the how, make sure to checkout [this documentation](performance.md) on a regular basis.


**Note:** Development continues as planned. Data-api is now ready to make "buffered-charts". Updates soon.