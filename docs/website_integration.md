# Rogue Circuit Website Integration

Circuit Alpha can run as a local browser app today and as a backend API
for the Rogue Circuit website later. The safest production shape is to keep the
trading service private, put a reverse proxy or website backend in front of it,
and require `ROGUE_QUANT_AUTH_TOKEN` for every write action.

## Runtime Modes

Set the deployment mode with:

```bash
export ROGUE_QUANT_MODE=paper
```

Available modes:

- `local`: local command center, no external access expected
- `paper`: external dashboard/API allowed, live trading locked
- `live_locked`: production-like API, live trading locked
- `live_enabled`: production mode that permits live trading checks to pass
- `maintenance`: read-only mode; write actions are blocked

Live trading still requires the lower-level trading settings to allow live
execution. The deployment mode is an additional product-level lock.

## Auth

Set a token before exposing the app beyond your machine:

```bash
export ROGUE_QUANT_AUTH_TOKEN="replace-with-a-long-random-token"
```

Send it on write requests:

```text
X-Rogue-Token: replace-with-a-long-random-token
```

`GET /api/state` remains readable for local dashboards. Keep the API private if
portfolio values should not be visible.

## Credential Vault

Kraken credentials can be encrypted through the browser app or API:

```http
POST /api/credentials/kraken
```

```json
{
  "api_key": "KRAKEN_KEY",
  "api_secret": "KRAKEN_SECRET"
}
```

The app writes encrypted data to `data/credential_vault.json` and the generated
Fernet key to `data/credential_vault.key`. Do not commit either file.

For a Kraken Pro spot key, grant only the trading permissions the app needs:

- Query Funds
- Query Open Orders & Trades
- Query Closed Orders & Trades
- Modify Orders
- Cancel/Close Orders

Do not grant Withdraw Funds.

## API Endpoints

- `GET /api/state`: portfolio, bot, strategy, audit, chart, and system state
- `POST /api/deposits`: record a deposit
- `POST /api/withdrawals`: record a withdrawal
- `POST /api/snapshots/manual`: record a manual portfolio value
- `POST /api/snapshots/kraken`: refresh Kraken valuation
- `POST /api/settings`: update risk controls
- `POST /api/credentials/kraken`: store encrypted Kraken credentials
- `POST /api/kraken/check`: validate Kraken credentials, target balance, and market availability
- `POST /api/kraken/use-target`: set the bot symbol to the configured target market
- `POST /api/trading/run-once`: execute one AI trading cycle
- `POST /api/bot/start`: start the background bot loop
- `POST /api/bot/stop`: stop the background bot loop
- `POST /api/emergency-stop`: stop trading and activate the kill switch
- `POST /api/resume`: clear the emergency stop

## Opportunity Alerts

The trading cycle can emit `OPPORTUNITY` alerts when a cryptocurrency has a
BUY signal that passes confidence and backtest filters. These alerts are meant
to flag candidates for review; they do not guarantee profit.

Tune the thresholds with:

```bash
export ROGUE_QUANT_OPPORTUNITY_MIN_CONFIDENCE=0.70
export ROGUE_QUANT_OPPORTUNITY_MIN_WIN_RATE=0.55
export ROGUE_QUANT_OPPORTUNITY_MIN_NET_PROFIT=0
```

If `ROGUE_QUANT_WEBHOOK_URL` is set, opportunity alerts are also sent to the
configured webhook.

## QUID Target Workflow

The default target asset is `QUID` and the default target symbol is `QUID/USD`.
Override them with:

```bash
export ROGUE_QUANT_TARGET_ASSET=QUID
export ROGUE_QUANT_TARGET_SYMBOL=QUID/USD
```

The dashboard requires three checks before it considers QUID ready for paper
automation:

- Kraken credentials are stored
- `QUID/USD` is available as a direct Kraken Pro market
- a positive QUID balance is found
- the bot has been explicitly switched to `QUID/USD`

Live trading remains locked unless deployment mode and lower-level live trading
settings are both deliberately enabled.

## Running The API

Local standard-library server:

```bash
python3 web_app.py
```

FastAPI adapter:

```bash
uvicorn api.fastapi_app:create_app --factory --host 127.0.0.1 --port 8765
```

When connecting from the Rogue Circuit website, prefer a website-owned backend
route that forwards allowed requests to this API. That keeps the trading token
off the public frontend and gives you one place for rate limits and user auth.
