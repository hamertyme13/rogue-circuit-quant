from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ml.features import FeatureConfig, MLFeatureEngine


@dataclass(frozen=True)
class DirectionDatasetConfig:

    horizon: int = 6
    neutral_threshold: float = 0.0
    target_column: str = "target_direction"
    future_return_column: str = "future_return"
    signal_column: str = "target_signal"


class DirectionPredictionDatasetBuilder:

    def __init__(
        self,
        feature_engine: MLFeatureEngine | None = None,
        config: DirectionDatasetConfig | None = None,
    ):

        self.feature_engine = feature_engine or MLFeatureEngine()
        self.config = config or DirectionDatasetConfig()

    def build(
        self,
        candles: pd.DataFrame,
    ) -> pd.DataFrame:

        if self.config.horizon <= 0:
            raise ValueError("Prediction horizon must be greater than zero.")

        features = self.feature_engine.build(candles)
        labels = self._labels(candles)
        dataset = features.merge(
            labels,
            on="timestamp",
            how="left",
            validate="one_to_one",
        )

        dataset = dataset.dropna().reset_index(drop=True)
        dataset[self.config.target_column] = dataset[
            self.config.target_column
        ].astype(int)
        dataset[self.config.signal_column] = dataset[
            self.config.signal_column
        ].astype(int)

        return dataset

    def split_xy(
        self,
        dataset: pd.DataFrame,
    ) -> tuple[pd.DataFrame, pd.Series]:

        feature_columns = self.feature_columns(dataset)

        return (
            dataset[feature_columns],
            dataset[self.config.target_column],
        )

    def feature_columns(
        self,
        dataset: pd.DataFrame,
    ) -> list[str]:

        excluded = set(self.feature_engine.config.passthrough_columns)
        excluded.update({
            self.config.future_return_column,
            self.config.target_column,
            self.config.signal_column,
        })

        return [
            column
            for column in dataset.columns
            if column not in excluded
        ]

    def _labels(
        self,
        candles: pd.DataFrame,
    ) -> pd.DataFrame:

        df = candles[["timestamp", "close"]].copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["close"] = df["close"].astype(float)
        df = df.sort_values("timestamp").reset_index(drop=True)

        future_close = df["close"].shift(-self.config.horizon)
        future_return = future_close / df["close"] - 1
        signal = self._signal(future_return)
        direction = (future_return > self.config.neutral_threshold).astype(
            "Int64"
        )
        direction[future_return.isna()] = pd.NA

        return pd.DataFrame({
            "timestamp": df["timestamp"],
            self.config.future_return_column: future_return,
            self.config.target_column: direction,
            self.config.signal_column: signal,
        })

    def _signal(
        self,
        future_return: pd.Series,
    ) -> pd.Series:

        signal = pd.Series(0, index=future_return.index, dtype="Int64")
        signal[future_return > self.config.neutral_threshold] = 1
        signal[future_return < -self.config.neutral_threshold] = -1
        signal[future_return.isna()] = pd.NA

        return signal


def default_direction_dataset_builder() -> DirectionPredictionDatasetBuilder:

    return DirectionPredictionDatasetBuilder(
        feature_engine=MLFeatureEngine(
            FeatureConfig(drop_warmup=True)
        )
    )
