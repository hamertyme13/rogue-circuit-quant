from __future__ import annotations

import pandas as pd

from models.constants import BUY, HOLD, SELL
from models.signal import Signal
from strategies.base import Strategy


class MeanReversionStrategy(Strategy):

    def __init__(
        self,
        window: int = 20,
        entry_zscore: float = 1.5,
        exit_zscore: float = 0.25,
    ):

        if window <= 1:
            raise ValueError("window must be greater than one.")

        if entry_zscore <= 0:
            raise ValueError("entry_zscore must be greater than zero.")

        self.window = window
        self.entry_zscore = entry_zscore
        self.exit_zscore = exit_zscore

    def generate_signals(
        self,
        df: pd.DataFrame,
    ) -> list[Signal]:

        if len(df) < self.window:
            return [self._hold(df.iloc[-1], confidence=0.0)]

        enriched = df.copy()
        enriched["rolling_mean"] = enriched["close"].rolling(self.window).mean()
        enriched["rolling_std"] = enriched["close"].rolling(self.window).std()
        latest = enriched.iloc[-1]
        rolling_std = latest["rolling_std"]

        if pd.isna(rolling_std) or rolling_std <= 0:
            return [self._hold(latest, confidence=0.0)]

        zscore = (latest["close"] - latest["rolling_mean"]) / rolling_std
        confidence = min(1.0, abs(zscore) / (self.entry_zscore * 2))

        if zscore <= -self.entry_zscore:
            return [self._signal(latest, BUY, confidence)]

        if zscore >= self.entry_zscore:
            return [self._signal(latest, SELL, confidence)]

        if abs(zscore) <= self.exit_zscore:
            return [self._hold(latest, confidence=0.2)]

        return [self._hold(latest, confidence=confidence)]

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
            strategy="MeanReversion",
        )

    def _hold(
        self,
        row,
        confidence,
    ) -> Signal:

        return self._signal(row, HOLD, confidence)
