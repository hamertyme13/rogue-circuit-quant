from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ml.regime import MarketRegimeClassifier, MarketRegimePrediction
from models.constants import HOLD
from models.signal import Signal
from strategies.base import Strategy


@dataclass(frozen=True)
class StrategyHealth:

    name: str
    score: float = 1.0
    enabled: bool = True


@dataclass(frozen=True)
class StrategyRouterConfig:

    min_strategy_score: float = 0.0
    min_regime_confidence: float = 0.15
    min_ml_confidence: float = 0.0
    default_strategy: str = "momentum"
    max_drawdown: float = 0.10


class AIStrategyRouter(Strategy):

    def __init__(
        self,
        strategies: dict[str, Strategy],
        regime_classifier: MarketRegimeClassifier | None = None,
        config: StrategyRouterConfig | None = None,
        strategy_health: dict[str, StrategyHealth] | None = None,
        risk_manager=None,
        model=None,
    ):

        self.strategies = strategies
        self.regime_classifier = regime_classifier or MarketRegimeClassifier()
        self.config = config or StrategyRouterConfig()
        self.strategy_health = strategy_health or {}
        self.risk_manager = risk_manager
        self.model = model

    def generate_signals(
        self,
        df: pd.DataFrame,
    ) -> list[Signal]:

        if not self._risk_allows_trade():
            return [self._hold(df, "RouterRisk")]

        regime = self.regime_classifier.classify_candles(df)
        selected_name = self.select_strategy(regime)

        if selected_name is None:
            return [self._hold(df, "RouterNoStrategy")]

        strategy = self.strategies[selected_name]
        signals = strategy.generate_signals(df)

        return [
            self._tag(signal, selected_name, regime)
            for signal in signals
        ]

    def select_strategy(
        self,
        regime: MarketRegimePrediction,
    ) -> str | None:

        if regime.confidence < self.config.min_regime_confidence:
            return self._enabled_strategy(self.config.default_strategy)

        candidates = self._candidates_for_regime(regime.regime)

        for candidate in candidates:
            enabled = self._enabled_strategy(candidate)
            if enabled:
                return enabled

        return self._enabled_strategy(self.config.default_strategy)

    def _candidates_for_regime(
        self,
        regime: str,
    ) -> list[str]:

        if regime in {"trend_up", "trend_down"}:
            return ["momentum", "breakout"]

        if regime == "chop":
            return ["mean_reversion"]

        if regime == "volatility_expansion":
            return ["breakout", "momentum"]

        if regime == "volatility_compression":
            return ["mean_reversion", "breakout"]

        return [self.config.default_strategy]

    def _enabled_strategy(
        self,
        name: str,
    ) -> str | None:

        if name not in self.strategies:
            return None

        health = self.strategy_health.get(
            name,
            StrategyHealth(name=name),
        )

        if not health.enabled:
            return None

        if health.score < self.config.min_strategy_score:
            return None

        if self._model_confidence() < self.config.min_ml_confidence:
            return None

        return name

    def _model_confidence(self) -> float:

        if self.model is None:
            return 1.0

        confidence = getattr(self.model, "confidence", None)

        if confidence is None:
            return 1.0

        return float(confidence)

    def _risk_allows_trade(self) -> bool:

        if self.risk_manager is None:
            return True

        can_open_trade = getattr(self.risk_manager, "can_open_trade", None)
        if callable(can_open_trade):
            return bool(can_open_trade())

        drawdown = getattr(self.risk_manager, "drawdown", 0.0)

        return float(drawdown) < self.config.max_drawdown

    def _tag(
        self,
        signal: Signal,
        selected_name: str,
        regime: MarketRegimePrediction,
    ) -> Signal:

        return Signal(
            timestamp=signal.timestamp,
            action=signal.action,
            price=signal.price,
            confidence=signal.confidence,
            strategy=(
                f"Router:{selected_name}:"
                f"{regime.regime}:{regime.confidence:.2f}"
            ),
        )

    def _hold(
        self,
        df: pd.DataFrame,
        strategy: str,
    ) -> Signal:

        latest = df.iloc[-1]

        return Signal(
            timestamp=latest["timestamp"],
            action=HOLD,
            price=float(latest["close"]),
            confidence=0.0,
            strategy=strategy,
        )
