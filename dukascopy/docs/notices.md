## Less updates

There have been a bit less updates and fixes. I was "completely into the transformers" for days. Now I have eliminated them-they are just not suitable for this, extended the default engine with temporal lookback features and after initial tests shown to be very promising I am back on the original track. Back to earth :)

## New Polars version

I have upgraded to a newer Python and a newer version of Polars. I saw that the unit-tests are broken and a lot of stuff has become deprecated. Only now i find out that stuff breaks on a newer Python version. 

I am fixing it. I will launch these fixes together with the new RPulsar engine. Somewhere this week.

## ML

Maybe a breakthrough. Standard transformers are very hard to use for very sparse events. The problem is the loss function. When you have only 1.3 percent of events it is very easy for a model to just predict 0 since it gives ~99 percent accuracy. I tried many things to get transformers to work, focal loss functions, additional penalties for being wrong, dynamic penalties, gaussian blur to make bottoms a multicandle event, sliding OOS windows to prevent it from memorizing timestamps and so on and on and on. The architecture complexity increased by magnitudes, so i decided to abandon the transformers.

Instead i extended the neuro-evolution with lookback properties. The new engine "can see in the past". It can detect "certain moves" in indicators leading up to the event. 

It may be a first breakthrough but I am heavily testing this first. 

Next on the list is regime detection.

What are you trying to achieve? Find rare precursor patterns before reversals. Exploit them.

What is the current focus of the research? Temporal pattern recognition across a broad search space. I will soon start the "killer-search". Still writing features for that.

One interesting observation is that, with this R(ecurrent)Pulsar, the models are way more transferable. 

## 🚀 Release Update: Developer UX & Surgical Maintenance

This project is a high-performance market research and analysis tool focused on feature engineering. While optimized for **"mechanical sympathy"** at the hardware level, these latest additions focus on improving the daily workflow for developers and researchers.




























