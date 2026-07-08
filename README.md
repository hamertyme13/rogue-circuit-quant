# Rogue Circuit Quant

An AI-powered quantitative cryptocurrency trading platform.

## Goals

- Historical backtesting
- Live paper trading
- Live Kraken execution
- Portfolio management
- AI strategy optimization
- Risk management
- Performance analytics

Built by Rogue Circuit Co.

## Automated Kraken Trading

Run the automated paper-trading loop:

```bash
python3 trade_live.py
```

The loop continuously downloads Kraken candles, re-optimizes strategy
parameters on a schedule, asks the AI strategy analyst to rank the most
profitable/risk-aware result, and executes BUY/SELL/HOLD signals.

Safety defaults:

- `PAPER_TRADING = True`
- `ALLOW_LIVE_TRADING = False`
- Kraken credentials are read from `KRAKEN_API_KEY` and `KRAKEN_API_SECRET`
- `MAX_ORDER_NOTIONAL` caps order size
- existing daily loss, drawdown, and open-position limits still apply

Only set `PAPER_TRADING = False` and `ALLOW_LIVE_TRADING = True` after
paper-trading results have been reviewed.

## Desktop Investment Dashboard

Run the local desktop app:

```bash
python3 desktop_app.py
```

The dashboard stores its investment ledger in SQLite at
`data/rogue_circuit_ledger.sqlite3`. It tracks deposits, withdrawals, portfolio
value snapshots, trade records, net growth, and growth percentage.

Use the dashboard to:

- add deposits and withdrawals
- record manual portfolio snapshots
- refresh current Kraken balances when API credentials are configured
- run one paper/live trading cycle through the existing trading engine
- start and stop the background bot service
- activate an emergency stop and resume trading afterward
- tune runtime risk controls, including order size, confidence, and loop timing
- review the decision journal, strategy performance, trade records, and alerts
- view recent ledger activity and the portfolio value chart

Package the desktop app with PyInstaller:

```bash
python3 scripts/package_desktop_app.py
```

If PyInstaller is not installed, the script will print the install command and
exit without changing the project.
