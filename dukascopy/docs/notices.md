
## ML

After a large session working on the ML side, I decided to abandon trying to replicate the eventdetect_ts approach to implementing the model and instead started adapting that specific library directly. The library already contains multiple models, and integrating them appears to be a much more straightforward path.

The transformer approach proved to be very difficult. I was constantly battling issues with the loss function and with the model memorizing timestamps. For example, it was very easy for the model to learn patterns like: “there are 800 zero bars and bar 801 is a one.” Alternatively, the model could simply predict zero for everything, which already yields ~99% accuracy due to the class imbalance.

This creates a kind of mathematical gravity well that is extremely difficult to escape without very advanced and highly customized training pipelines.

Therefore, I decided to fall back to the implementation by Azib et al.

The "custom ensemble" will also get replaced with this library's metalearner. Later more on this.

Time was not "thrown away". Learned a great deal on "AI" (matrix math).

Had a little bit of time, this eventdetector_ts library is great. I got it training after only 15 minutes of work...

```sh
Model: "transformer"
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Layer (type)                  ┃ Output Shape              ┃         Param # ┃ Connected to               ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ input (InputLayer)            │ (None, 76, 50)            │               0 │ -                          │
├───────────────────────────────┼───────────────────────────┼─────────────────┼────────────────────────────┤
│ multi_head_attention          │ (None, 76, 50)            │         415,794 │ input[0][0], input[0][0],  │
│ (MultiHeadAttention)          │                           │                 │ input[0][0]                │
├───────────────────────────────┼───────────────────────────┼─────────────────┼────────────────────────────┤
│ add (Add)                     │ (None, 76, 50)            │               0 │ input[0][0],               │
│                               │                           │                 │ multi_head_attention[0][0] │
├───────────────────────────────┼───────────────────────────┼─────────────────┼────────────────────────────┤
│ layer_normalization           │ (None, 76, 50)            │             100 │ add[0][0]                  │
│ (LayerNormalization)          │                           │                 │                            │
├───────────────────────────────┼───────────────────────────┼─────────────────┼────────────────────────────┤
│ dense (Dense)                 │ (None, 76, 50)            │           2,550 │ layer_normalization[0][0]  │
├───────────────────────────────┼───────────────────────────┼─────────────────┼────────────────────────────┤
│ dropout_1 (Dropout)           │ (None, 76, 50)            │               0 │ dense[0][0]                │
├───────────────────────────────┼───────────────────────────┼─────────────────┼────────────────────────────┤
│ add_1 (Add)                   │ (None, 76, 50)            │               0 │ layer_normalization[0][0], │
│                               │                           │                 │ dropout_1[0][0]            │
├───────────────────────────────┼───────────────────────────┼─────────────────┼────────────────────────────┤
│ multi_head_attention_1        │ (None, 76, 50)            │         415,794 │ add_1[0][0], add_1[0][0],  │
│ (MultiHeadAttention)          │                           │                 │ add_1[0][0]                │
├───────────────────────────────┼───────────────────────────┼─────────────────┼────────────────────────────┤
│ add_2 (Add)                   │ (None, 76, 50)            │               0 │ input[0][0],               │
│                               │                           │                 │ multi_head_attention_1[0]… │
├───────────────────────────────┼───────────────────────────┼─────────────────┼────────────────────────────┤
│ layer_normalization_1         │ (None, 76, 50)            │             100 │ add_2[0][0]                │
│ (LayerNormalization)          │                           │                 │                            │
├───────────────────────────────┼───────────────────────────┼─────────────────┼────────────────────────────┤
│ dense_1 (Dense)               │ (None, 76, 50)            │           2,550 │ layer_normalization_1[0][… │
├───────────────────────────────┼───────────────────────────┼─────────────────┼────────────────────────────┤
│ dropout_3 (Dropout)           │ (None, 76, 50)            │               0 │ dense_1[0][0]              │
├───────────────────────────────┼───────────────────────────┼─────────────────┼────────────────────────────┤
│ add_3 (Add)                   │ (None, 76, 50)            │               0 │ layer_normalization_1[0][… │
│                               │                           │                 │ dropout_3[0][0]            │
├───────────────────────────────┼───────────────────────────┼─────────────────┼────────────────────────────┤
│ global_average_pooling1d      │ (None, 50)                │               0 │ add_3[0][0]                │
│ (GlobalAveragePooling1D)      │                           │                 │                            │
├───────────────────────────────┼───────────────────────────┼─────────────────┼────────────────────────────┤
│ dense_2 (Dense)               │ (None, 1)                 │              51 │ global_average_pooling1d[… │
└───────────────────────────────┴───────────────────────────┴─────────────────┴────────────────────────────┘
 Total params: 836,939 (3.19 MB)
 Trainable params: 836,939 (3.19 MB)
 Non-trainable params: 0 (0.00 B)
2026-03-07 16:37:13 [INFO] eventdetector_ts.models: None
2026-03-07 16:37:13 [INFO] eventdetector_ts.models: Fitting of transformer...
Epoch 1/250
...
```

Next week i should have the metalearner running and have the first results. Had to be sure this is fairly easy to work with. It actually is. Not bad for a academic library. Thumbs up.

Couldnt let it: quick peek at performance-since it outputs histograms immediately. This is what it tells me: it detects bottom events with a 5-7 bar lead-time. So it sees something in the indicators that "causally" aligns and happens a few days before a bottom is in. Don't know exactly what yet, but next week I will know the exact rules. Need to test this on the live edge soon.

Bidirectional RNN is currently the strongest "scout" for 4H bottoms.

## 🚀 Release Update: Developer UX & Surgical Maintenance

This project is a high-performance market research and analysis tool focused on feature engineering. While optimized for **"mechanical sympathy"** at the hardware level, these latest additions focus on improving the daily workflow for developers and researchers.














