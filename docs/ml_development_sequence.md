# ML Development Sequence

This roadmap keeps the machine-learning work incremental, testable, and
separate from live trading until it has enough evidence.

## Sprint 10.1 - ML Feature Engine

Status: implemented.

The feature engine lives in `ml/features.py` and turns OHLCV candles into
model-ready features without future leakage. Current features include:

- multi-window returns and log returns
- momentum and EMA distance features
- RSI
- rolling volatility and range position
- ATR percentage
- Bollinger band position
- volume z-score and volume ratio
- candle body, range, wick, and close-location features
- cyclical time-of-day and day-of-week features

## Sprint 10.2 - Direction Prediction Dataset

Status: implemented.

The direction dataset builder lives in `ml/dataset.py`. It aligns each feature
row with a future-return label outside the feature engine, then drops rows where
warmup values or future labels are unavailable. Current outputs include:

- `future_return`: close-to-future-close return over the configured horizon
- `target_direction`: binary up/down class for model training
- `target_signal`: `-1`, `0`, or `1` signal class using the neutral threshold

This keeps future information out of the feature engine while still creating a
forward-looking supervised-learning target.

## Sprint 10.3 - XGBoost Model

Status: implemented.

The XGBoost model wrapper lives in `ml/xgboost_model.py`. It trains against the
direction dataset, stores the exact feature columns used for training, returns
up-probability predictions, and can save or load a model artifact for later
paper-trading evaluation.

XGBoost is imported lazily so the rest of the app and tests can still run before
the optional ML runtime is installed. Install project dependencies before real
training with `python3 -m pip install -r requirements.txt`.

## Sprint 10.4 - Model Evaluation And Walk-Forward ML Testing

Status: implemented.

The ML evaluator lives in `ml/evaluation.py`. It reports precision, recall,
specificity, F1, Brier score, confidence, confusion-matrix counts, and
forward-return behavior. It also supports rolling walk-forward folds over either
an existing direction dataset or raw candle history.

The model should not influence trading until these reports show useful
out-of-sample evidence across multiple market conditions.

## Sprint 10.5 - Combine ML And Momentum Signals

Status: implemented.

The ML signal filter lives in `strategies/ml_signal_filter.py`. It wraps an
existing strategy, reads the latest model probability, boosts aligned BUY or
SELL signals, and vetoes conflicting signals to HOLD. It fails closed by default
so an untrained or unavailable model cannot accidentally create a trade.

## Sprint 10.6 - Market-Regime Classifier

Status: implemented.

The market-regime classifier lives in `ml/regime.py`. It classifies trend up,
trend down, chop, volatility expansion, volatility compression, and neutral
regimes from the same ML feature set used by the direction model.

## Sprint 10.7 - Mean-Reversion And Breakout Strategies

Status: implemented.

The mean-reversion and breakout strategies live in `strategies/mean_reversion.py`
and `strategies/breakout.py`. They now generate normal BUY, SELL, and HOLD
signals with confidence scores so they can be evaluated by the same backtesting,
paper-trading, ML-filtering, and future routing pipeline.

## Sprint 10.8 - AI Strategy Router

Status: implemented.

The strategy router lives in `strategies/router.py`. It chooses momentum,
mean-reversion, or breakout strategies based on market regime, strategy health,
optional ML confidence, and risk-manager permission. It returns HOLD when risk
controls block trading or no healthy strategy is available.

## Sprint 10.9 - Extended Paper-Trading Validation

Status: implemented.

The paper validator lives in `live/paper_validation.py`. It evaluates paper runs
for minimum cycle count, closed-trade count, growth, drawdown, executed events,
and opportunity rate before the system can be considered for live deployment.

## Sprint 11 - Carefully Controlled Live Deployment

Status: implemented as a live-readiness gate.

The browser command center now exposes a live-readiness gate that combines paper
validation, deployment mode, credential status, target-asset readiness, and
emergency-stop state. Live trading remains locked unless every gate passes.

## Sprint 12 - Shadow Trading And Live Execution Safety

Status: implemented with live submission locked by default.

The execution-safety layer lives in `live/execution_safety.py`. It adds staged
paper, shadow, and limited-live modes; Kraken API permission inspection;
pair-minimum and precision validation; free-balance checks; configurable fee,
slippage, and cash-reserve estimates; and unique client order identifiers.

Shadow mode uses live Kraken balances and market rules to validate orders but
never submits them. Limited-live mode additionally requires the paper-validation
gate, safe API permissions, a live-enabled deployment, an explicit environment
unlock, and a typed confirmation. Confirmed fills remain required before local
positions are updated, and the emergency stop attempts to cancel open Kraken
orders.

## Sprint 13 - Shadow Validation And Outcome Tracking

Status: implemented.

Circuit Alpha now keeps a persistent journal of shadow order previews across
all selected markets. On the next observation for a market, it resolves the
previous proposal against the new price and reports the Kraken-valid order
rate, estimated cost rate, profitable-after-cost outcome rate, and average net
return. Limited-live readiness now requires enough healthy shadow evidence in
addition to the paper-trading and account-safety gates.

## Sprint 14 - Daily Paper Sessions And Rolling Evidence

Status: implemented.

The command center now stores a local-time daily schedule and starts a bounded
paper session at most once per calendar day. Each session forces paper mode,
uses the bot service's existing retry and backoff behavior, stops after the
configured cycle count, and records starts or safety-related skips in the audit
log. The schedule survives app restarts and steadily builds the paper evidence
required by the deployment gate without leaving the bot running forever.

## Sprint 15 - Automated Multi-Market Universe Refresh

Status: implemented.

Before each daily paper session, Circuit Alpha can refresh liquid Kraken
markets, run the existing strategy analysis, and select a diversified shortlist.
The selector excludes cash and stablecoin base assets, duplicate quote markets,
strategies without completed test trades, and non-positive risk-adjusted scores.
The resulting crypto-only set is persisted and used by the bounded paper run.
Automated scanning can be disabled or sized independently from the schedule.

## Sprint 16 - Rolling Market Health And Quarantine

Status: implemented.

Circuit Alpha now combines resolved shadow outcomes and closed paper trades into
a per-market health profile. Markets remain in learning status until they have
enough evidence, become healthy when their rolling win rate and shadow returns
clear the configured quality thresholds, and are automatically quarantined when
repeated evidence deteriorates. The daily universe selector excludes quarantined
markets even when a fresh backtest ranks them highly, and the dashboard exposes
the sample count, win rate, shadow return, and paper PnL behind each status.

## Sprint 17 - Multi-Asset Portfolio Allocation

Status: implemented.

The paper trader can now hold several selected cryptocurrency markets at once.
Every proposed buy passes through a portfolio allocator that enforces a maximum
number of open markets, a total exposure ceiling, a per-market exposure ceiling,
a protected cash reserve, and the existing per-order cap. Allocation decisions
are visible in the command center and the limits persist across app restarts.
The same sizing path feeds shadow previews, while live order submission remains
disabled by default and behind all prior deployment gates.

## Sprint 18 - Persistent Paper Portfolio And Evidence

Status: implemented.

Paper cash, open and closed trades, market prices, equity history, high-water
mark, cycle count, and aggregate execution and opportunity evidence are now
stored in the SQLite ledger after every completed paper cycle. On startup the
trader reconstructs its portfolio and reconnects the risk and position managers
to that restored state. Paper-readiness progress therefore survives desktop and
background-service restarts, while Shadow and Limited Live cycles do not inflate
the durable paper-validation counters.
Daily market refreshes also retain every currently open paper symbol so restored
positions continue receiving prices and exit signals until they are closed.

## Sprint 19 - Per-Market Live Candidate Promotion

Status: implemented.

Live readiness is no longer tied to the originally held QUID asset. Every
selected market now receives its own promotion report based on rolling health,
resolved shadow sample count, Kraken-valid preview rate, profitable-after-cost
rate, and average shadow return. Limited Live requires at least one eligible
candidate, and its buy path enforces an in-memory symbol allowlist. A persisted
Limited Live mode is downgraded to Paper on every app restart, requiring the
readiness checks and typed confirmation again before any new live buy.

## Sprint 20 - Automatic Shadow Validation Follow-Up

Status: implemented.

Each scheduled paper session can now transition automatically into a short,
bounded Shadow phase after its paper cycles finish. Shadow uses current Kraken
balances, prices, and order constraints to collect per-market validation
evidence without submitting an order. The phase is configurable, survives an
app restart while pending, skips safely when credentials or safety conditions
are unavailable, and always returns the app to Paper mode when complete.
Manual Stop and Emergency Stop cancel any pending follow-up.

## Sprint 21 - Balance-Aware Shadow Order Validation

Status: implemented.

Shadow BUY validation is now independent of paper-only open positions, paper
drawdown guards, and simulated cash. It proposes no more than the configured
order cap, sizes the preview down to the actual free Kraken quote balance, and
rechecks affordability after Kraken precision rounding. This path never calls
order submission. Paper and Limited Live retain their existing allocation and
risk enforcement.

Readiness now evaluates bounded recent evidence rather than lifetime history:
the latest 25 observations for the overall Shadow gate and the latest 10
resolved observations per market. Older evidence remains in the ledger for
audit and diagnostics but no longer permanently prevents recovery after a
validation defect is corrected.

## Sprint 22 - Actionable Shadow Evidence Collection

Status: implemented.

Shadow journaling now records every actionable BUY that reaches a Kraken order
preview, even when the signal does not meet the stricter opportunity-alert
threshold. Opportunity notifications remain selective and unchanged. HOLD,
SELL-without-position, market-error, and other events without a fresh preview
cannot reuse an older preview or create misleading validation evidence. This
lets bounded daily Shadow sessions advance the readiness sample counts whenever
the strategy produces a genuine buy proposal.

## Sprint 23 - Bounded Market Work And Responsive Stops

Status: implemented.

Kraken requests now use an explicit 8-second ccxt timeout with automatic ccxt
failure retries disabled. A scan or trading cycle stops taking new markets after
90 seconds, and Stop is checked between markets. A partially completed cycle
reports its reason in the service message and alert history. The daily scheduler
waits briefly at process startup so the local HTTP endpoint can bind first.
These limits are cooperative: an in-flight request or strategy calculation must
return before the current market can be interrupted.

## Sprint 24 - Qualified Paper Evidence

Status: implemented.

A paper run advances live-readiness cycle and opportunity counts only when
every selected market returned a fresh BUY, SELL, or HOLD signal with a price.
Runs with Kraken errors, missing markets, emergency-stop results, or a partial
time-budget result remain in the trading journal and are counted separately as
unverified runs. Version 1 saved portfolios are restored intact, while their
old cycle counts are labeled legacy and excluded from readiness because those
counts did not prove complete market coverage. New verified counters persist in
version 2 of the paper runtime state.
