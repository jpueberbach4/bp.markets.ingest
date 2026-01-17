# About this project

Welcome. A core focus of this work is extracting as much performance as possible from a standard laptop. This document serves as an overview of how I achieved approximately 3 million candles per second in resampling performance on commodity hardware. It also provides an in-depth discussion of market data caveats and outlines a practical approach to transforming raw data into reliable, usable datasets.

The goal of this document is to share the lessons I’ve learned so others can benefit substantially from these insights.

## Project scope

The project’s scope is centered on building a foundational data layer on which a high-performance backtesting engine can be built. Making raw market data usable presents many challenges, as most data formats and inputs do not accurately reflect real market conditions. Data is often poorly aligned, inconsistent with actual market behavior, or otherwise flawed—frequently forcing users to rely on expensive, “cleaned” data feeds.

This project addresses the full range of issues associated with raw market data. MetaTrader 4 (MT4) has been reverse-engineered and translated into approximately 1,000 lines of core logic, enabling accurate and reliable data handling without dependence on paid data providers.

## The why, how it started

I have been involved in trading for quite some time-from around the Lehmann Brothers debacle and the early-bitcoin era- with periods of inactivity, but fully committed over the past year. During this time, I spent a significant amount of effort trying to optimize my workflow, only to repeatedly run into various limitations. The process was inefficient and overly tedious.

Eventually, I took a closer look at the JSON data format provided by Dukascopy and realized it could serve as a strong alternative to my existing approach. I scrapped my previous solutions—which relied on external data sources—and set out to match this feed as closely as possible to what I observed in MT4. I wrote a downloader that retrieved per-day data for each asset, starting with EUR/USD, and attempted to resample it to replicate MT4’s behavior. From the outset, I used a cascaded design.

This turned out to be a breakthrough. On the first attempt, I achieved nearly perfect alignment. I then generalized the software, built an aggregated feed covering all my primary forex pairs, and resampled them across all required timeframes. This marked the beginning of the ETL process. Data quality was significantly better than anything I had previously worked with.

At that stage—about seven weeks ago, this was built in about 7 weeks time—everything was still stored as CSV which quickly became impractical. I needed multi-symbol aggregation and efficient data extraction, which meant building an extraction tool. This is how the builder was born.

To be continued...