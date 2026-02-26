## ML Experiment

A day off means: no cognitive load. Just documentation.

# Singularities

**Open-source neuroevolution forge for discovering high-conviction, sparse market signals — without raw price or volume.**

A hardened, GPU-accelerated system that evolves small neural networks purely from technical indicators + derived **Market Kinetics** (velocity, acceleration, presence).

Note: the kinetics feature is at this moment unreliable, was shuvved under the carpet for a bit, because a specific model built on cross-divergency and multi-tf-rsi was performing really good. It will be reintroduced soon. First i need to split up the major singularities class. It may still work, but untested atm. Hold your horsies. It will be back (and tested) soon.

Limits: strictly excludes raw OHLCV to force discovery of higher-order, physics-like confluences.

Why? I see the markets as a physics-alike system and don't want (to risk) memorization on prices.

Benefit? Models will work inter-asset. Which already is proven to be a correct thought.

Current focus? detecting asymmetric market bottoms on 4h timeframes (~0.3–0.6% density).

**Status (February 2026):**  

- Observed forward F1 in the 0.46–0.59 range on sparse (~0.3–0.6%) asymmetric event detection, depending on model and market regime.
- Models are transferable, not locked into a single asset
- Still rough but nearing real-beta rapidly
- Neuroevolution outperforms RandomForest quite dramatically
- GPU-only but CPU-only support will be added. 
- One observed behavior appears highly promising but requires prolonged forward validation (see [signals.gif](../images/signals.gif)).
- Currently have 11 universes of which 3 are generating very promising models
- One model frontruns the actual bottoms by 2-5 H4 candles consistently, which is interesting.
- Supports Out of sample testing. Another repo has real walkforward testing but is currently unstable.
  It is too advanced for my current knowledge but this is increasing at lightspeed.
- Currently only GELU and Sigmoid activation functions but others are explored (Relu, leaky Relu and others)
- System is not yet fully overloadable with custom classes, it misses overloading for lenses functions (will soon be in)
- Default MilkyWay is optimized for a 8GB RTX3070 GPU
- Elites on F1 and Precision are persistently stored in slot 0 and 1 and always survive.
- **Advice:** for a card having more VRAM, tune GPU chunk and population. Monitor with nvtop.
- **Advice:** Lower-F1 models often exhibit lower signal density, better regime stability, and reduced overfitting, which can outperform high-F1 models out of sample. Check using `example-ml-pt` indicator.
- **Advice:** watch your temps if running on laptop. I regret it that i didnt build temperature protection before. Now its in.

**Important:** Still **research-grade** — requires brutal validation. Do not trust it blindly!

**Not yet a plug-and-play money printer.**

**Signals as a permission filter. If signals, go look at the chart. Know that a bottom is soon in. Like that.**

## What's next

- Amazing model 3750 forward validation
- Diagnostic tools to evaluate/confirm performance
- Diagnostic walk-forward backtest -> report
- Perhaps, if have time: PNL testing (first want to see the walkforward test)
- Currently cosmic-themed logs. Will add string-table to support boring "enterprise" log-messages.
- CPU support
- Split up of the massive singularities class
- Configurable destination directories for checkpoints/logs (parameterizing HaleBopp)
- Degrade Voyager and EventHorizon (MilleniumFalcon and Pulsar outperform, use these two)

What else? see [todo.md](../docs/todo.md) document.

## Core Principles

- Markets as physical systems with hidden non-linear laws  
- Real alpha in **indicator confluences**, not price memorization  
- **No raw OHLCV** — only derived indicators + macro proxies  
- Extreme sparsity + precision bias → rare, high-R:R signals  
- Out of sample testing
- Open forge: extend with your macro, COT, order-flow, gravitational/flow theories

## Features

- Strict indicator-only input (raw price/volume filtered out)   
- Configurable Out Of Sample testing (default 30% is out of sample)
- Pessimistic robust scoring (`min` F1 across windows)  
- Precision-biased fitness (`prec^exp` ramp)
- Extreme penalization of bad-precision population
- Density/recall floors + hard reject logic  
- Leakage smoke test (`assert` early F1 < 0.30)  
- Radiation injection (40% fresh DNA) on stagnation  
- Mass extinction (100% reset) on prolonged stagnation  
- GPU thermal throttling (park if >87 °C)  
- Async persistence (Hale-Bopp comet)  
- Champion/Elite deployment (full-history retrain + saved normalization)  
- YAML-configurable + factory pattern extensibility  
- Cosmic-themed observability (logs, vitality ranks, reject %, weight stats)

## Quick Start

YOU NEED A CUDA CAPABLE GPU! 

```sh
pip install -r ml/requirements.txt
```

This install will take a while.

Then you can add your own universes. See `config/ml/universes/*.yaml` for an example.

You can run this stuff from the root `./run-ml.sh --universe MilkyWay` (or whatever you called your universe).

Checkpoints (models) are currently written, fixed, in the dukascopy/checkpoints directory.

When models have been generated you can evaluate performance using the `example-ml-pt` indicator in your interface. It needs the model filename as input.

You can use it to generate models, used for additional filtering on your existing signals.

It is "decent" in its current state, but its ongoing research item of me.

Results of the past are by no means predictive of the future. 

## IMPORTANT

Your models will be extremely flawed if any indicators peak into the future. Generally these are indicators that use rolling(center=True) or use any other next-bar information. So before you jump off your chair when you reach an F1 > 0.5, triple-check, no, quadruple check your features for leakage!

## IMPORTANT

When you are running this on a laptop, make sure your hotness_max and hotness_min are configured properly. Running this stuff `hot` for a longer period is VERY BAD (trust me) for your VRMs and VRAM chips. I was a bit sad over a week ago because i didnt pay attention to this.

## IMPORTANT (DONT USE, MAY BE BROKEN ATM - FIX SOON)

The Kinematics normalizer explodes every indicator value into 4 dimensions. Velocity, Direction, Acceleration and magnitude. Use a high gene count if you enable this. Typically one third of the total number of dimensions. Use high powered GPU as well if you want to grind through 300 + dimensions. Kinematics looks very promising but i am still grinding. I will make this stuff multigpu capable, later.

Expect it to grind for a couple of days before it returns something really useful. 

**For now: dont use kinematics. Try first with normal indicator values.**

## Extending the code

The code can be easily extend by just specifying your own classes in a java-alike notation witin the config-file.

`config.user.ml.comets.Halley` (Example is present in config directory)

Extensions are possible for:

- comets
- flights
- normalizers
- singularities
- universes

Note: custom classes need to extend the specific baseclasses.

Note: additional abstractions will be added soon

## Structure

```sh
Universe (ABC)                  ← Defines the "environment" (data + features)
  └── MilkyWay (concrete)       ← Specific implementation (EUR-USD/4h, config-driven)
  └── Andromeda (experimental)  ← Experimental (not in repo, milkyway works well)

Comet (ABC)                     ← Async persistence / data transport
  └── HaleBopp (concrete)       ← Disk-based logger/checkpointer
  └── Halley (example)          ← Example in `config.user/ml/comets.py`

Normalizer (ABC)                ← Feature scaling
  └── Redshift (concrete)       ← Z-score normalizer
  └── Kinematics (concrete)     ← Establishes laws like velocity, direction, magnitude,.. \

Lens (ABC)                      ← Loss function
  └── GravitationalLens (concrete) ← Focal loss with alpha/gamma

Singularity (ABC)               ← Core computational engine (the "reactor")
  └── EventHorizonSingularity (concrete) ← Population-based neuroevolution + hardening (deprecated)
  └── PulsarSingularity (concrete) ← Population-based neuroevolution

Flight (ABC)                    ← Orchestration / training loop
  └── Voyager (concrete)        ← The main runner (warp, thermal management, extinction) (deprecated)
  └── MilleniumFalcon (concrete) ← Hardened main runner (warp, thermal management, extinction)

```
