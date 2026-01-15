## [0.2.0-stable] - 2025-12-03

### Changed
- **Repository curation**: History cleaned to showcase production-ready architecture
- **Calendar alignment**: Weekly candles now match Dukascopy charts exactly  
- **Documentation**: Enhanced README with clearer setup, usage, and troubleshooting

### For Existing Users
If you cloned this repository before 2025-12-03:

```bash
# Update to the cleaned version
cd /path/to/repo
git fetch origin
git reset --hard origin/main

# Rebuild data to apply calendar alignment fixes
./rebuild-weekly.sh
```

## [0.3.0-stable] - 2025-12-04

### Changed
- **Configuration**: Everything is now configurable through YAML
- **Documentation**: Updated README with instructions

## [0.4.0-stable] - 2025-12-07

### Changed
- **ETL**: Moved to etl subfolder (non-breaking)
- **Feature**: Powerful parquet builder added
- **Documentation**: Updated README with instructions

### For Existing Users
Non-breaking.

## [0.5.0-stable] - 2025-12-14

### Changed
- **Feature**: Parquet/CSV Builder updates (--mt4 and --list support)
- **Feature**: Added time_shift_ms to support MT4 alignment
- **Config**: Added Dukascopy MT4 configuration example
- **Documentation**: Updated README with instructions

### For Existing Users
Non-breaking. 

## [0.6.0-stable] - 2025-12-31

- **Feature**: DST (Daylight Saving Time) support has been added
- **Feature**: Session support
- **Feature**: Exotic indices now supported
- **Feature**: Major simplification on configuration (inheritance support)
- **Feature**: Improved robustness and exception handling
- **Feature**: Vectorized session resolution
- **Feature**: Session boundaries for post-processing rules
- **Feature**: Beta version of Panama-backadjustment with aligned resample-support
- **Feature**: JSON/JSONP/CSV HTTP API
- **Feature**: Static HTML service with charting example
- **Feature**: Schema validation on config
- **Documentation**: Updated README with instructions

### For Existing Users
Non-breaking. 

## [0.6.5-stable] - 2026-01-07

- **Feature**: Binary mode introduced
- **Feature**: IO Layer is abstracted
- **Feature**: HTTP service code optimization
- **Feature**: 40+ indicators added
- **Feature**: Increased API limits
- **Documentation**: Updated README with instructions

### For Existing Users
Non-breaking. 

## [0.6.6-beta] - 2026-01-15

- **Feature**: New indicator.html interface
- **Feature**: New index.html interface
- **Feature**: Increased API limits
- **Feature**: Removal of DuckDB on API
- **Documentation**: Updated README with instructions

### For Existing Users
!!BREAKING!! FOR TEXT MODE USERS. SWITCH TO BINARY MODE. SEE DOCUMENTATION.
YOU WILL GET A LOT OF BENEFITS WITH BINARY MODE



