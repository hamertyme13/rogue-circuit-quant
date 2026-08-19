from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = (
    "timestamp",
    "open",
    "high",
    "low",
    "close",
    "volume",
)


@dataclass(frozen=True)
class FeatureConfig:

    return_windows: tuple[int, ...] = (1, 3, 6, 12)
    momentum_windows: tuple[int, ...] = (3, 6, 12, 24)
    volatility_windows: tuple[int, ...] = (6, 12, 24)
    ema_windows: tuple[int, ...] = (8, 21, 55)
    rsi_windows: tuple[int, ...] = (14,)
    volume_windows: tuple[int, ...] = (12, 24)
    atr_window: int = 14
    bollinger_window: int = 20
    drop_warmup: bool = True
    passthrough_columns: tuple[str, ...] = field(
        default_factory=lambda: ("timestamp", "open", "high", "low", "close", "volume")
    )


class MLFeatureEngine:

    def __init__(self, config: FeatureConfig | None = None):

        self.config = config or FeatureConfig()

    def build(
        self,
        candles: pd.DataFrame,
    ) -> pd.DataFrame:

        self._validate(candles)
        df = candles.copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp").reset_index(drop=True)

        numeric_columns = ["open", "high", "low", "close", "volume"]
        df[numeric_columns] = df[numeric_columns].astype(float)

        features = df[list(self.config.passthrough_columns)].copy()
        self._add_return_features(df, features)
        self._add_trend_features(df, features)
        self._add_volatility_features(df, features)
        self._add_volume_features(df, features)
        self._add_candle_features(df, features)
        self._add_time_features(df, features)

        features = features.replace([np.inf, -np.inf], np.nan)

        if self.config.drop_warmup:
            features = features.dropna().reset_index(drop=True)

        return features

    def feature_columns(self, features: pd.DataFrame) -> list[str]:

        return [
            column
            for column in features.columns
            if column not in self.config.passthrough_columns
        ]

    def _add_return_features(
        self,
        df: pd.DataFrame,
        features: pd.DataFrame,
    ):

        close = df["close"]
        log_close = np.log(close)
        log_return = log_close.diff()
        features["return_1"] = close.pct_change()
        features["log_return_1"] = log_return

        for window in self.config.return_windows:
            features[f"return_{window}"] = close.pct_change(window)
            features[f"log_return_{window}"] = log_close.diff(window)

    def _add_trend_features(
        self,
        df: pd.DataFrame,
        features: pd.DataFrame,
    ):

        close = df["close"]

        for window in self.config.momentum_windows:
            features[f"momentum_{window}"] = close / close.shift(window) - 1

        for window in self.config.ema_windows:
            ema = close.ewm(span=window, adjust=False).mean()
            features[f"ema_{window}_distance"] = close / ema - 1

        ema_windows = sorted(self.config.ema_windows)
        if len(ema_windows) >= 2:
            fast = close.ewm(span=ema_windows[0], adjust=False).mean()
            slow = close.ewm(span=ema_windows[-1], adjust=False).mean()
            features["ema_fast_slow_spread"] = fast / slow - 1

        for window in self.config.rsi_windows:
            features[f"rsi_{window}"] = self._rsi(close, window)

    def _add_volatility_features(
        self,
        df: pd.DataFrame,
        features: pd.DataFrame,
    ):

        close = df["close"]
        log_return = np.log(close).diff()

        for window in self.config.volatility_windows:
            features[f"volatility_{window}"] = log_return.rolling(window).std()
            rolling_high = df["high"].rolling(window).max()
            rolling_low = df["low"].rolling(window).min()
            features[f"range_position_{window}"] = (
                (close - rolling_low) / (rolling_high - rolling_low)
            )

        atr = self._atr(df, self.config.atr_window)
        features[f"atr_{self.config.atr_window}_pct"] = atr / close

        middle = close.rolling(self.config.bollinger_window).mean()
        deviation = close.rolling(self.config.bollinger_window).std()
        upper = middle + (deviation * 2)
        lower = middle - (deviation * 2)
        features[f"bollinger_position_{self.config.bollinger_window}"] = (
            (close - lower) / (upper - lower)
        )

    def _add_volume_features(
        self,
        df: pd.DataFrame,
        features: pd.DataFrame,
    ):

        volume = df["volume"]

        for window in self.config.volume_windows:
            rolling_mean = volume.rolling(window).mean()
            rolling_std = volume.rolling(window).std()
            features[f"volume_zscore_{window}"] = (
                (volume - rolling_mean) / rolling_std
            )
            features[f"volume_ratio_{window}"] = volume / rolling_mean

    def _add_candle_features(
        self,
        df: pd.DataFrame,
        features: pd.DataFrame,
    ):

        candle_range = df["high"] - df["low"]
        body = df["close"] - df["open"]
        upper_wick = df["high"] - df[["open", "close"]].max(axis=1)
        lower_wick = df[["open", "close"]].min(axis=1) - df["low"]

        features["candle_body_pct"] = body / df["open"]
        features["candle_range_pct"] = candle_range / df["open"]
        features["upper_wick_ratio"] = upper_wick / candle_range
        features["lower_wick_ratio"] = lower_wick / candle_range
        features["close_location"] = (df["close"] - df["low"]) / candle_range

    def _add_time_features(
        self,
        df: pd.DataFrame,
        features: pd.DataFrame,
    ):

        timestamp = pd.to_datetime(df["timestamp"])
        minute_of_day = timestamp.dt.hour * 60 + timestamp.dt.minute
        day_of_week = timestamp.dt.dayofweek

        features["minute_sin"] = np.sin(2 * np.pi * minute_of_day / 1440)
        features["minute_cos"] = np.cos(2 * np.pi * minute_of_day / 1440)
        features["day_sin"] = np.sin(2 * np.pi * day_of_week / 7)
        features["day_cos"] = np.cos(2 * np.pi * day_of_week / 7)

    def _rsi(
        self,
        close: pd.Series,
        window: int,
    ) -> pd.Series:

        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        average_gain = gain.rolling(window).mean()
        average_loss = loss.rolling(window).mean()
        relative_strength = average_gain / average_loss

        return 100 - (100 / (1 + relative_strength))

    def _atr(
        self,
        df: pd.DataFrame,
        window: int,
    ) -> pd.Series:

        previous_close = df["close"].shift(1)
        true_range = pd.concat(
            [
                df["high"] - df["low"],
                (df["high"] - previous_close).abs(),
                (df["low"] - previous_close).abs(),
            ],
            axis=1,
        ).max(axis=1)

        return true_range.rolling(window).mean()

    def _validate(self, candles: pd.DataFrame):

        missing = [
            column
            for column in REQUIRED_COLUMNS
            if column not in candles.columns
        ]

        if missing:
            raise ValueError(
                "Candles are missing required columns: "
                + ", ".join(missing)
            )
