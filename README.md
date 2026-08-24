# Circuit Alpha

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

## Browser Command Center

Run the browser app:

```bash
python3 web_app.py
```

Then open:

```text
http://127.0.0.1:8765
```

Install or refresh the macOS Desktop launcher:

```bash
python3 scripts/install_macos_launcher.py --target ~/Desktop
```

This creates `Circuit Alpha.app` with a custom Rogue Circuit icon. Opening
the app starts the local browser command center and launches it in your browser.

The browser app uses the same SQLite ledger, Kraken valuation logic, bot
service, emergency stop, risk controls, and trading journal as the desktop app.
It serves a Rogue Circuit themed frontend plus local JSON API endpoints, making
it easier to connect to the Rogue Circuit website later.

New browser/API capabilities include:

- optional token auth with `ROGUE_QUANT_AUTH_TOKEN`
- encrypted Kraken credential vault storage
- deployment modes through `ROGUE_QUANT_MODE`
- strategy performance, decision journal, audit log, and paper/live comparison
- richer chart data for equity, drawdown, and daily PnL views
- webhook/email notification routing hooks, including high-confidence
  opportunity alerts
- FastAPI adapter for production-style API hosting

Run the FastAPI adapter:

```bash
uvicorn api.fastapi_app:create_app --factory --host 127.0.0.1 --port 8765
```

Useful environment variables:

- `ROGUE_QUANT_AUTH_TOKEN`: requires `X-Rogue-Token` on write requests
- `ROGUE_QUANT_MODE`: `local`, `paper`, `live_locked`, `live_enabled`, or `maintenance`
- `ROGUE_QUANT_TARGET_ASSET`: target balance asset, defaults to `QUID`
- `ROGUE_QUANT_TARGET_SYMBOL`: target market, defaults to `QUID/USD`
- `ROGUE_QUANT_LIVE_SYMBOLS`: comma-separated bot symbols, defaults to `BTC/USD`
- `ROGUE_QUANT_WEBHOOK_URL`: optional JSON webhook for critical alerts
- `ROGUE_QUANT_EMAIL_TO`: placeholder email route for future SMTP delivery
- `ROGUE_QUANT_OPPORTUNITY_MIN_CONFIDENCE`: BUY signal confidence threshold
- `ROGUE_QUANT_OPPORTUNITY_MIN_WIN_RATE`: backtested win-rate threshold
- `ROGUE_QUANT_OPPORTUNITY_MIN_NET_PROFIT`: backtested profit threshold
- `ROGUE_QUANT_EXECUTION_MODE`: `paper`, `shadow`, or `limited_live`
- `ROGUE_QUANT_SHADOW_VALIDATION_MIN_SAMPLES`: resolved shadow proposals required before limited live (default `25`)
- `ROGUE_QUANT_SHADOW_VALIDATION_MIN_VALID_RATE`: minimum Kraken-valid preview rate (default `0.90`)
- `ROGUE_QUANT_SHADOW_VALIDATION_MIN_PROFITABLE_RATE`: minimum profitable-after-cost outcome rate (default `0.50`)
- `ROGUE_QUANT_SHADOW_VALIDATION_MAX_COST_RATE`: maximum average estimated fee and slippage rate (default `0.02`)
- `ROGUE_QUANT_SHADOW_VALIDATION_MIN_AVERAGE_RETURN`: minimum average shadow return after estimated costs (default `0`)
- `ROGUE_QUANT_ALLOW_LIVE_TRADING`: explicit live-order unlock; defaults false
- `ROGUE_QUANT_LIVE_TAKER_FEE_RATE`: fee estimate used by order previews
- `ROGUE_QUANT_LIVE_SLIPPAGE_RATE`: slippage reserve used by order previews
- `ROGUE_QUANT_LIVE_CASH_RESERVE_RATE`: cash buffer retained around live buys

Opportunity alerts mean a symbol passed the configured signal and backtest
filters. They are not profit guarantees.

For Kraken Pro connection, create a spot API key with Query Funds, Query Open
Orders & Trades, Query Closed Orders & Trades, Modify Orders, and Cancel/Close
Orders permissions. Do not grant Withdraw Funds. Store the key in the browser
credential vault, run Check Kraken / QUID, then use Use QUID for Bot if the
market and balance checks pass.

See `docs/website_integration.md` for the Rogue Circuit website connection plan.
See `docs/ml_development_sequence.md` for the Sprint 10 ML roadmap.

The macOS installer also registers a per-user background service. Circuit Alpha
starts at login and remains available for bounded daily paper sessions even when
its browser tab is closed. The schedule is configured in the Daily Paper Session
panel and never submits live orders.
