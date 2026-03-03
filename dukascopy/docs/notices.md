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



