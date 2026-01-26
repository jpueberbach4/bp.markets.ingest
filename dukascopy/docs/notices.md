<u>MT4 is decoded.</u>

What's next?

This moves to seperate (clean) repository by 31st of January.

I’ve merged the `clean-version` branch into `main`.

I’m currently building a powerful ML-driven bottom sniper. I’m still deciding whether to release it with this repository—features like this usually provide a real edge and are typically kept private. It’s an H4 bottom sniper; the H4 timeframe provides just enough data to train it effectively.

Until I’ve made a final decision, there’s an example included that demonstrates how such a sniper can be built. It’s only an example. An experienced quant should be able to infer how the general machine-learning workflow works by reviewing it. ML is essentially feature engineering followed by model construction. What’s critical is that the indicator delivers exactly the same feature set to the probe (prediction) routines as was used during training.

I’m relatively new to this area myself, but I’m getting up to speed quickly. When working with ML, make sure to implement proper safety gates. As confidence levels increase, additional validation logic should kick in—for example, confirmation using other assets or well-known candle patterns such as gravestones, shooting stars, long-legged dojis, iSHS, SHS, engulfings, and similar formations.

All of this can be implemented in a lightning-fast indicator on this platform. See the examples directory for introductory ML code.


