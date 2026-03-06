
## ML

After a large session working on the ML side, I decided to abandon trying to replicate the eventdetect_ts approach to implementing the model and instead started adapting that specific library directly. The library already contains multiple models, and integrating them appears to be a much more straightforward path.

The transformer approach proved to be very difficult. I was constantly battling issues with the loss function and with the model memorizing timestamps. For example, it was very easy for the model to learn patterns like: “there are 800 zero bars and bar 801 is a one.” Alternatively, the model could simply predict zero for everything, which already yields ~99% accuracy due to the class imbalance.

This creates a kind of mathematical gravity well that is extremely difficult to escape without very advanced and highly customized training pipelines.

Therefore, I decided to fall back to the implementation by Azib et al.

## 🚀 Release Update: Developer UX & Surgical Maintenance

This project is a high-performance market research and analysis tool focused on feature engineering. While optimized for **"mechanical sympathy"** at the hardware level, these latest additions focus on improving the daily workflow for developers and researchers.









