
## ML

There is still work to do. Some bottoms are V-shapes, others are consolidating for some time. For even better detection some additional changes are needed. 

I am currently looking into the works of 

- ~~Prof. Terry Lyons (Oxford)~~
- Bai, Kolter, Koltun, 2018
- Perry Kaufman and
- John Ehlers

to solve the final issues.

Sorry this takes a bit. It's advanced. 

Update: getting really really close now. Rough path was not the solution. The solution seems to be in an other path (Macro-stencil CNN).

![Getting close](../images/gettingclose.png)

This is with a DEFAULT SET of features and FULLY OOS. Never seen data. Works on live edge. Almost tradeable. Almost. One of the tops is missed. The biggest one. It frontruns it. Seems a feature-issue. So am re-adding macro-features.

Quite a journey. 

Kinematics is also back on the table. Detecting tops cleanly is (much) harder than detecting bottoms.

Well-known sayings about this: Markets take the stairs up and the elevator down | Bottoms are an event. Tops are a process.

I am also adding matrix profiles to increase precision. Tricky part is to elinimate lookahead bias everywhere. I am using matrix profiles to pre-select what features to be fed into the neural networks. Matrix profiles tell me something about the correlation between indicators and tops. Eg do they make about the same pattern everytime on a top -> preselect.

This is a very challenging problem that has been chased by many traders and professionals. It is impossible to get a 100 percent accuracy because of the nature of markets. Markets are nonstationary, noisy and extremely efficient in killing edges. I am atm in a deep research phase. Playing with many different neural nets and even reinforcement learning. 

While the code hasnt been updated for some time now, know that deep research work is in progress. 

I know that i am trying to solve the unsolvable but a steady 54-60 percent precision is enough (using proper RR).

This research may take another couple of weeks. Eventually i will release something working :)

I am close but not satisfied.

Concept drift is my biggest enemy atm.

## 🚀 Release Update: Developer UX & Surgical Maintenance

This project is a high-performance market research and analysis tool focused on feature engineering. While optimized for **"mechanical sympathy"** at the hardware level, these latest additions focus on improving the daily workflow for developers and researchers.







































