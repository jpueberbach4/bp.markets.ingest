## ML Experiment

# Event Horizon Reactor

**Open-source neuroevolution forge for discovering high-conviction, sparse market signals — without raw price or volume.**

A production-hardened, GPU-accelerated system that evolves small neural networks purely from technical indicators + derived **Market Kinetics** (velocity, acceleration, presence).  

Strictly excludes raw OHLCV to force discovery of higher-order, physics-like confluences.

Current focus: detecting asymmetric market bottoms on 4h timeframes (~0.3–0.6% density).

**Status (February 2026):**  
Promising directional generalization (EURUSD → GBPUSD transfer with same frozen model), F1 range 0.46–0.59 on unseen forward data, very low signal density (~0.36%).  
Still **research-grade** — requires brutal validation. Not yet a plug-and-play money printer.

## Core Principles

- Markets as physical systems with hidden non-linear laws  
- Real alpha in **indicator confluences**, not price memorization  
- **No raw OHLCV** — only derived indicators + kinetics + macro proxies  
- Extreme sparsity + precision bias → rare, high-R:R signals  
- Walk-forward per individual, pessimistic min-F1 scoring, leakage hardening  
- Open forge: extend with your macro, COT, order-flow, gravitational/flow theories

## Features

- Strict indicator-only input (raw price/volume filtered out)  
- Automatic **Market Kinetics** (velocity, acceleration, presence per feature)  
- Multi-window walk-forward validation per genome  
- Pessimistic robust scoring (`min` F1 across windows)  
- Precision-biased fitness (`prec^exp` ramp)  
- Density/recall floors + hard reject logic  
- Leakage smoke test (`assert` early F1 < 0.30)  
- Radiation injection (40% fresh DNA) on stagnation  
- Mass extinction (100% reset) on prolonged stagnation  
- GPU thermal throttling (park if >87 °C)  
- Async persistence (Hale-Bopp comet)  
- Champion deployment (full-history retrain + saved normalization)  
- YAML-configurable + factory pattern extensibility  
- Cosmic-themed observability (logs, vitality ranks, reject %, weight stats)


Note: this document was AI generated based on an other "private repo". A heavily overengineered one that doesnt work correctly. This version is simpler but works much better for simple NN signal-finding. Moral of the story: Above may not completely reflect the "real situation. **Documentation subject to change.**

## Quick Start

YOU NEED A CUDA CAPABLE GPU! 

```sh
pip install -r ml/requirements.txt
```

This install will take a while.

The you can add your own universes. See `config/ml/universes/*.yaml` for an example.

You can run this stuff from the root `./run-ml.sh --universe MilkyWay` (or whatever you called your universe).

Checkpoints (models) are currently written, fixed, in the dukascopy/checkpoints directory.

When models have been generated you can evaluate performance using the `example-ml-pt` indicator in your interface. It needs the model filename as input.

You can use it to generate models, used for additional filtering on your existing signals.

It is "decent" in its current state, but its ongoing research item of me.

Results of the past are by no means predictive of the future. 

## IMPORTANT

Your models will be extremely flawed if any indicators peak into the future. Generally these are indicators that use rolling(center=True) or use any other next-bar information. So before you jump off your chair when you reach an F1 > 0.5, triple-check, no, quadruple check your features for leakage!

## Structure

```sh
Universe (ABC)                  ← Defines the "environment" (data + features)
  └── MilkyWay (concrete)       ← Specific implementation (EUR-USD/4h, config-driven)

Comet (ABC)                     ← Async persistence / data transport
  └── HaleBopp (concrete)       ← Disk-based logger/checkpointer

Normalizer (ABC)                ← Feature scaling
  └── Redshift (concrete)       ← Z-score normalizer

Lens (ABC)                      ← Loss function
  └── GravitationalLens (concrete) ← Focal loss with alpha/gamma

Singularity (ABC)               ← Core computational engine (the "reactor")
  └── EventHorizonSingularity (concrete) ← Population-based neuroevolution + hardening

Flight (ABC)                    ← Orchestration / training loop
  └── Voyager (concrete)        ← The main runner (warp, thermal management, extinction)
```