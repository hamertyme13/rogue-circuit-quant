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
