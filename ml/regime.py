from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

from ml.features import MLFeatureEngine


MarketRegime = Literal[
    "trend_up",
    "trend_down",
    "chop",
    "volatility_expansion",
    "volatility_compression",
    "neutral",
]


@dataclass(frozen=True)
class MarketRegimeConfig:

    trend_threshold: float = 0.015
    chop_momentum_threshold: float = 0.005
    chop_range_low: float = 0.35
    chop_range_high: float = 0.65
    volatility_expansion_ratio: float = 1.25
    volatility_compression_ratio: float = 0.75
    confidence_scale: float = 2.0


@dataclass(frozen=True)
class MarketRegimePrediction:

    regime: MarketRegime
    confidence: float
    trend_score: float
    volatility_ratio: float
    range_position: float


class MarketRegimeClassifier:

    def __init__(
        self,
        feature_engine: MLFeatureEngine | None = None,
        config: MarketRegimeConfig | None = None,
    ):

        self.feature_engine = feature_engine or MLFeatureEngine()
        self.config = config or MarketRegimeConfig()

    def classify_candles(
        self,
        candles: pd.DataFrame,
    ) -> MarketRegimePrediction:

        features = self.feature_engine.build(candles)

        return self.classify_features(features)

    def classify_features(
        self,
        features: pd.DataFrame,
    ) -> MarketRegimePrediction:

        if features.empty:
            raise ValueError("Cannot classify an empty feature set.")

        latest = features.iloc[-1]
        trend_score = self._trend_score(latest)
        volatility_ratio = self._volatility_ratio(latest)
        range_position = self._range_position(latest)
        regime = self._regime(
            trend_score,
            volatility_ratio,
            range_position,
        )

        return MarketRegimePrediction(
            regime=regime,
            confidence=self._confidence(
                regime,
                trend_score,
                volatility_ratio,
                range_position,
            ),
            trend_score=trend_score,
            volatility_ratio=volatility_ratio,
            range_position=range_position,
        )

    def _regime(
        self,
        trend_score: float,
        volatility_ratio: float,
        range_position: float,
    ) -> MarketRegime:

        if volatility_ratio >= self.config.volatility_expansion_ratio:
            return "volatility_expansion"

        if volatility_ratio <= self.config.volatility_compression_ratio:
            return "volatility_compression"

        if trend_score >= self.config.trend_threshold:
            return "trend_up"

        if trend_score <= -self.config.trend_threshold:
            return "trend_down"

        if (
            abs(trend_score) <= self.config.chop_momentum_threshold
            and self.config.chop_range_low
            <= range_position
            <= self.config.chop_range_high
        ):
            return "chop"

        return "neutral"

    def _trend_score(
        self,
        row: pd.Series,
    ) -> float:

        values = [
            self._value(row, "momentum_12"),
            self._value(row, "momentum_24"),
            self._value(row, "ema_fast_slow_spread"),
        ]

        return float(sum(values) / len(values))

    def _volatility_ratio(
        self,
        row: pd.Series,
    ) -> float:

        short = self._value(row, "volatility_6")
        long = self._value(row, "volatility_24")

        if long <= 0:
            return 1.0

        return float(short / long)

    def _range_position(
        self,
        row: pd.Series,
    ) -> float:

        return self._value(row, "range_position_24", default=0.5)

    def _confidence(
        self,
        regime: MarketRegime,
        trend_score: float,
        volatility_ratio: float,
        range_position: float,
    ) -> float:

        if regime == "trend_up":
            raw = trend_score / self.config.trend_threshold
        elif regime == "trend_down":
            raw = abs(trend_score) / self.config.trend_threshold
        elif regime == "volatility_expansion":
            raw = volatility_ratio / self.config.volatility_expansion_ratio
        elif regime == "volatility_compression":
            raw = self.config.volatility_compression_ratio / max(
                volatility_ratio,
                0.000001,
            )
        elif regime == "chop":
            range_centered = 1 - abs(range_position - 0.5) * 2
            momentum_calm = 1 - (
                abs(trend_score)
                / max(self.config.chop_momentum_threshold, 0.000001)
            )
            raw = max(0.0, (range_centered + momentum_calm) / 2)
        else:
            raw = 0.5

        return float(max(0.0, min(1.0, raw / self.config.confidence_scale)))

    def _value(
        self,
        row: pd.Series,
        column: str,
        default: float = 0.0,
    ) -> float:

        value = row.get(column, default)

        if pd.isna(value):
            return default

        return float(value)
