from __future__ import annotations

import pandas as pd

from models.constants import BUY, HOLD, SELL
from models.signal import Signal
from strategies.base import Strategy


class BreakoutStrategy(Strategy):

    def __init__(
        self,
        lookback: int = 20,
        volume_multiplier: float = 1.2,
    ):

        if lookback <= 1:
            raise ValueError("lookback must be greater than one.")

        if volume_multiplier <= 0:
            raise ValueError("volume_multiplier must be greater than zero.")

        self.lookback = lookback
        self.volume_multiplier = volume_multiplier

    def generate_signals(
        self,
        df: pd.DataFrame,
    ) -> list[Signal]:

        if len(df) <= self.lookback:
            return [self._hold(df.iloc[-1], confidence=0.0)]

        previous = df.iloc[-self.lookback - 1:-1]
        latest = df.iloc[-1]
        resistance = previous["high"].max()
        support = previous["low"].min()
        average_volume = previous["volume"].mean()
        volume_ratio = self._volume_ratio(
            latest["volume"],
            average_volume,
        )

        if (
            latest["close"] > resistance
            and volume_ratio >= self.volume_multiplier
        ):
            return [
                self._signal(
                    latest,
                    BUY,
                    self._confidence(latest["close"], resistance, volume_ratio),
                )
            ]

        if (
            latest["close"] < support
            and volume_ratio >= self.volume_multiplier
        ):
            return [
                self._signal(
                    latest,
                    SELL,
                    self._confidence(support, latest["close"], volume_ratio),
                )
            ]

        return [self._hold(latest, confidence=0.0)]

    def _confidence(
        self,
        upper,
        lower,
        volume_ratio,
    ) -> float:

        price_extension = abs(float(upper) / float(lower) - 1)
        volume_strength = min(1.0, volume_ratio / (self.volume_multiplier * 2))

        return float(min(1.0, 0.5 + price_extension + volume_strength / 2))

    def _volume_ratio(
        self,
        latest_volume,
        average_volume,
    ) -> float:

        if average_volume <= 0:
            return 1.0

        return float(latest_volume / average_volume)

    def _signal(
        self,
        row,
        action,
        confidence,
    ) -> Signal:

        return Signal(
            timestamp=row["timestamp"],
            action=action,
            price=float(row["close"]),
            confidence=float(confidence),
            strategy="Breakout",
        )

    def _hold(
        self,
        row,
        confidence,
    ) -> Signal:

        return self._signal(row, HOLD, confidence)
