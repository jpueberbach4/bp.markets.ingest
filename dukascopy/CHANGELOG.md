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
Non-breaking. Meet the power of Parquet and DuckDB :)

## [0.5.0-staging] - 2025-12-10

### Changed
- **Feature**: CSV Builder with --mt4 support
- **Feature**: Added time_shift_ms to support MT4 alignment
- **Feature**: Building towards full MT4 compatability
- **Documentation**: Updated README with instructions

### For Existing Users
Non-breaking. 