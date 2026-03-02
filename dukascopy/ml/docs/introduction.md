# Introduction

Note: this documentation is heavily AI-assisted and awaiting review.

## Introduction to the Pulsar Hybrid Neuro-Evolution System

In the world of quantitative trading, we often face a "needle in a haystack" problem: finding a small set of technical indicators that reliably predict a specific market event. The Pulsar architecture you see in `pulsar.py` and `pulsar_core.py` is a specialized hybrid system designed to solve this.

It combines Neural Networks (the "brains" that process data) with Evolutionary Algorithms (the "survival of the fittest" logic that picks the best inputs). Instead of a human trader guessing which indicators work, Pulsar "evolves" a population of mini-models, testing thousands of combinations until it finds the "alpha" strategy.

## Core Concepts: How Neuro-Evolution Works

Imagine you have 1,000 different traders in a room. Each trader is given a random set of 16 indicators (the gene_count) and a unique set of weights (their personal "gut feeling" on how to use those indicators).

- Population & Genomes: The PulsarCore initializes a "population" of models. Each model's "DNA" (genome) consists of the specific features it looks at and the mathematical weights assigned to them.

- The Forward Pass: Each model processes the market data through a neural network structure (forward method), producing a probability score.

- Selection (Survival of the Fittest): In the evolve method, we rank these models based on their performance (F1 score). The bottom performers are discarded, while the "Champions" are kept.

- Crossover & Mutation: This is the "breeding" phase. We take two successful models and swap some of their features (Crossover) to see if the combination is better. Occasionally, we swap a feature for a completely random one (Mutation) to discover new opportunities.

## What is this Typically Used For?

This system is built for Quantitative Research and Baseline Building. It is specifically designed to:

- Feature Selection: Automatically identifying which 16 indicators out of hundreds actually matter.

- Strategy Discovery: Finding non-linear relationships between indicators that a human might miss.

- Baseline Validation: Establishing a "factory spec" ground truth for a strategy before trying to optimize it further.

## Why This Solution for Sparse Event Detection?

Market "signals" (like a 2% breakout or a specific reversal pattern) are rare. If you use standard machine learning, the model might just learn to "never trade" because it's right 99% of the time (if the event only happens 1% of the time).

Pulsar solves this through:

- Target Density: The code includes a kl_penalty that forces the model to seek out a specific frequency of signals (e.g., 1% of the time) rather than just being "safe" and silent.

- F1 Score Optimization: Instead of just "Accuracy," it focuses on the F1 Score, which balances Precision (not being wrong) and Recall (not missing the move).

## General Concepts: Bias, Weighting, and Activations

To understand the forward pass in pulsar_core.py, think of it as a multi-step filter:

- Weights (W1, W2): These represent the "importance" of a signal. A higher weight means that specific indicator has a bigger impact on the final trade decision.

- Bias (B1, B2): This is the "threshold of conviction." For example, $B2$ is initialized at -2.0, meaning the model starts out "skeptical" and requires strong evidence from the indicators to trigger a "Buy" signal.

- Activation (GELU): The F.gelu function is a "gate." It allows strong signals to pass through while suppressing weak noise, introducing the non-linearity needed to model complex markets.

## Mathematical Concepts

The engine uses several high-level mathematical techniques to stay grounded:

- 1. The Objective Function (The Lens)The system doesn't just look at profit; it uses a precision_exp (Precision Exponent). This penalizes "noisy" models heavily, ensuring that when the model says "Trade," it has high conviction.

- 2. KL Divergence Penalty (KL(current_mean) || target_density)

This math (found in run_generation) acts as a "behavioral anchor". It prevents the model from evolving into a "black box" that either over-trades or never trades at all.

- 3. Xavier/Kaiming Initialization

Notice the weights are initialized with np.sqrt(2.0 / self.gene_count). This is a mathematical standard that ensures the signals neither explode into infinity nor vanish to zero as they pass through the layers.



