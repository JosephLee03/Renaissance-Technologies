# SA Intraday CTA MVP

This project implements an intraday CTA system for CZCE SA single-product trading.

## Architecture

- Detailed architecture documentation: [docs/architecture.md](docs/architecture.md)
- Design pattern mapping and trade-offs: [docs/design_patterns.md](docs/design_patterns.md)
- TCA methodology and implementation details: [docs/tca_framework.md](docs/tca_framework.md)

## Scope

- Data: 1-minute bars + level-1 ticks
- Holding period: intraday only (< 1 day)
- Strategy: DualThrust breakout (no factor/model dependency)
- Backtest: event-style bar decision + tick execution simulation
- Cost/TCA: pre-trade + intra-day + post-trade decomposition (IS/VWAP/RPM/Z-score)
- Persistence: SQLite
- Monitoring: Dash + Plotly
- Logging: real-time run logs + backtest event logs

## Requirement Coverage

- Strategy: DualThrust intraday CTA
- Self-built backtest: custom event-driven engine with risk controls
- Execution system: tick-level execution simulator with spread/slippage/impact/fee
- GUI: equity, drawdown, position, daily PnL, TCA, execution flow
- Database: SQLite tables for signals, orders, fills, trades, equity, TCA
- TCA: summary and hourly decomposition
- TCA细化: pre-trade prediction, intra-day adaptive analysis, post-trade IS decomposition

## Quick Start

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Run a pipeline slice:

```bash
python scripts/run_pipeline.py --start-day 20250701 --end-day 20250731
```

3. Start GUI:

```bash
python scripts/run_gui.py
```

## Project Layout

```text
config/default.yaml           # Runtime configuration
docs/architecture.md          # System architecture documentation
docs/design_patterns.md       # Design pattern implementation guide
docs/tca_framework.md         # TCA framework and formulas
scripts/run_pipeline.py       # End-to-end backtest entrypoint
scripts/run_data_audit.py     # Data quality checks
scripts/run_gui.py            # Monitoring dashboard
src/sa_cta/                  # Core package
src/sa_cta/architecture/     # Pattern-based orchestration layer
src/sa_cta/pipeline.py       # Backward-compatible facade entrypoint
src/sa_cta/logging_system.py # Runtime logging system
src/sa_cta/signal.py         # DualThrust signal generation
src/sa_cta/backtest.py       # Backtest engine
src/sa_cta/execution.py      # Tick-level execution simulator
src/sa_cta/tca.py            # Trading cost analysis
src/sa_cta/gui/app.py        # Dash monitor
```

