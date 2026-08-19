from __future__ import annotations

from dataclasses import dataclass, replace

import pandas as pd

from ml.dataset import DirectionPredictionDatasetBuilder
from models.constants import BUY, HOLD, SELL
from models.signal import Signal
from strategies.base import Strategy


@dataclass(frozen=True)
class MLSignalFilterConfig:

    buy_probability_floor: float = 0.55
    sell_probability_ceiling: float = 0.45
    fail_closed: bool = True
    strategy_name: str = "Momentum+ML"


class MLSignalFilterStrategy(Strategy):

    def __init__(
        self,
        base_strategy: Strategy,
        model,
        dataset_builder: DirectionPredictionDatasetBuilder | None = None,
        config: MLSignalFilterConfig | None = None,
    ):

        self.base_strategy = base_strategy
        self.model = model
        self.dataset_builder = (
            dataset_builder or DirectionPredictionDatasetBuilder()
        )
        self.config = config or MLSignalFilterConfig()

    def generate_signals(
        self,
        df: pd.DataFrame,
    ) -> list[Signal]:

        base_signals = self.base_strategy.generate_signals(df)
        prediction = self._prediction(df)

        return [
            self._filter_signal(signal, prediction.probability_up)
            for signal in base_signals
        ]

    def _prediction(
        self,
        df: pd.DataFrame,
    ):

        try:
            dataset = self.dataset_builder.build(df)
            if dataset.empty:
                raise ValueError("ML dataset did not produce usable rows.")

            return self.model.predict_latest(dataset)
        except Exception:
            if self.config.fail_closed:
                return _ClosedPrediction()

            raise

    def _filter_signal(
        self,
        signal: Signal,
        probability_up: float,
    ) -> Signal:

        if signal.action == BUY:
            if probability_up < self.config.buy_probability_floor:
                return self._hold(signal)

            return self._with_confidence(
                signal,
                probability_up,
            )

        if signal.action == SELL:
            if probability_up > self.config.sell_probability_ceiling:
                return self._hold(signal)

            return self._with_confidence(
                signal,
                1 - probability_up,
            )

        return replace(
            signal,
            strategy=self.config.strategy_name,
        )

    def _with_confidence(
        self,
        signal: Signal,
        ml_alignment: float,
    ) -> Signal:

        adjusted_confidence = min(
            1.0,
            signal.confidence * (0.5 + ml_alignment),
        )

        return replace(
            signal,
            confidence=adjusted_confidence,
            strategy=self.config.strategy_name,
        )

    def _hold(
        self,
        signal: Signal,
    ) -> Signal:

        return replace(
            signal,
            action=HOLD,
            confidence=0.0,
            strategy=self.config.strategy_name,
        )


class _ClosedPrediction:

    probability_up = 0.5
