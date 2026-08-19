import pandas as pd

from ml.dataset import (
    DirectionDatasetConfig,
    DirectionPredictionDatasetBuilder,
)
from ml.features import FeatureConfig, MLFeatureEngine
from models.constants import BUY, HOLD, SELL
from models.signal import Signal
from strategies.base import Strategy
from strategies.ml_signal_filter import MLSignalFilterStrategy


class StaticStrategy(Strategy):

    def __init__(
        self,
        action,
        confidence=0.8,
    ):

        self.action = action
        self.confidence = confidence

    def generate_signals(
        self,
        df,
    ):

        latest = df.iloc[-1]

        return [
            Signal(
                timestamp=latest["timestamp"],
                action=self.action,
                price=latest["close"],
                confidence=self.confidence,
                strategy="Static",
            )
        ]


class StaticPrediction:

    def __init__(
        self,
        probability_up,
    ):

        self.probability_up = probability_up


class StaticModel:

    def __init__(
        self,
        probability_up,
    ):

        self.probability_up = probability_up

    def predict_latest(
        self,
        dataset,
    ):

        return StaticPrediction(self.probability_up)


class BrokenModel:

    def predict_latest(
        self,
        dataset,
    ):

        raise RuntimeError("not trained")


def candle_frame(rows=80):
    timestamps = pd.date_range(
        "2026-01-01",
        periods=rows,
        freq="5min",
    )
    close = [
        100 + index
        for index in range(rows)
    ]

    return pd.DataFrame({
        "timestamp": timestamps,
        "open": close,
        "high": [value + 1 for value in close],
        "low": [value - 1 for value in close],
        "close": close,
        "volume": [
            100 + index % 5
            for index in range(rows)
        ],
    })


def dataset_builder():
    return DirectionPredictionDatasetBuilder(
        feature_engine=MLFeatureEngine(
            FeatureConfig(drop_warmup=False)
        ),
        config=DirectionDatasetConfig(horizon=1),
    )


def test_ml_signal_filter_boosts_aligned_buy_signal():
    strategy = MLSignalFilterStrategy(
        base_strategy=StaticStrategy(BUY, confidence=0.8),
        model=StaticModel(probability_up=0.75),
        dataset_builder=dataset_builder(),
    )

    signal = strategy.generate_signals(candle_frame())[0]

    assert signal.action == BUY
    assert signal.confidence == 1.0
    assert signal.strategy == "Momentum+ML"


def test_ml_signal_filter_vetoes_conflicting_buy_signal():
    strategy = MLSignalFilterStrategy(
        base_strategy=StaticStrategy(BUY),
        model=StaticModel(probability_up=0.40),
        dataset_builder=dataset_builder(),
    )

    signal = strategy.generate_signals(candle_frame())[0]

    assert signal.action == HOLD
    assert signal.confidence == 0.0


def test_ml_signal_filter_boosts_aligned_sell_signal():
    strategy = MLSignalFilterStrategy(
        base_strategy=StaticStrategy(SELL, confidence=0.8),
        model=StaticModel(probability_up=0.20),
        dataset_builder=dataset_builder(),
    )

    signal = strategy.generate_signals(candle_frame())[0]

    assert signal.action == SELL
    assert signal.confidence == 1.0


def test_ml_signal_filter_fails_closed_to_hold():
    strategy = MLSignalFilterStrategy(
        base_strategy=StaticStrategy(BUY),
        model=BrokenModel(),
        dataset_builder=dataset_builder(),
    )

    signal = strategy.generate_signals(candle_frame())[0]

    assert signal.action == HOLD
    assert signal.confidence == 0.0
