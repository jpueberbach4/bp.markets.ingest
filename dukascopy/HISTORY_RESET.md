# Repository History Reset - December 2025

## Why We Reset
This project started as an experimental hobby project and has now reached a stable, production-ready state. The previous commit history contained hundreds of minor AI-suggested README optimizations and micro-adjustments that obscured the actual code evolution.

## What Changed
- **Commit history**: Cleared ~200+ noise commits, preserving architectural intent
- **Calendar alignment**: Fixed weekly candle alignment to match Dukascopy charts
- **Documentation**: Consolidated into a single, clear README
- **Status**: Transitioned from "experimental" to "stable tool"

## For Developers
**No backup exists of the pre-reset commits.** This is a small, focused project (488 lines of actual code). The most significant work was in the documentation.

If you cloned before 2025-12-03:
```bash
cd /path/to/repo
git fetch origin
git reset --hard origin/main
# Rebuild required due to calendar alignment changes
./rebuild-weekly.sh
```
