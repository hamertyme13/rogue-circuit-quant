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
