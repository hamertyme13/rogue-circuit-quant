from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from ml.dataset import DirectionPredictionDatasetBuilder


@dataclass(frozen=True)
class XGBoostTrainingConfig:

    n_estimators: int = 250
    max_depth: int = 3
    learning_rate: float = 0.05
    subsample: float = 0.8
    colsample_bytree: float = 0.8
    objective: str = "binary:logistic"
    eval_metric: str = "logloss"
    random_state: int = 42
    n_jobs: int = 1
    extra_params: dict = field(default_factory=dict)


@dataclass
class DirectionPrediction:

    probability_up: float
    predicted_direction: int
    confidence: float


class XGBoostDirectionModel:

    def __init__(
        self,
        dataset_builder: DirectionPredictionDatasetBuilder | None = None,
        config: XGBoostTrainingConfig | None = None,
        model=None,
        feature_columns: list[str] | None = None,
    ):

        self.dataset_builder = (
            dataset_builder or DirectionPredictionDatasetBuilder()
        )
        self.config = config or XGBoostTrainingConfig()
        self.model = model
        self._feature_columns = feature_columns or []

    @property
    def feature_columns(self) -> list[str]:

        return list(self._feature_columns)

    def train(
        self,
        dataset: pd.DataFrame,
    ):

        x, y = self.dataset_builder.split_xy(dataset)
        self._feature_columns = list(x.columns)
        self.model = self._new_classifier()
        self.model.fit(x, y)

        return self

    def predict_proba(
        self,
        features: pd.DataFrame,
    ) -> np.ndarray:

        self._require_trained()
        x = features[self._feature_columns]
        probabilities = self.model.predict_proba(x)

        return np.asarray(probabilities)[:, 1]

    def predict_latest(
        self,
        features: pd.DataFrame,
    ) -> DirectionPrediction:

        probability_up = float(self.predict_proba(features.tail(1))[0])
        predicted_direction = int(probability_up >= 0.5)

        return DirectionPrediction(
            probability_up=probability_up,
            predicted_direction=predicted_direction,
            confidence=max(probability_up, 1 - probability_up),
        )

    def save(
        self,
        path: str | Path,
    ):

        self._require_trained()
        self.model.save_model(str(path))

    def load(
        self,
        path: str | Path,
        feature_columns: list[str],
    ):

        self.model = self._new_classifier()
        self.model.load_model(str(path))
        self._feature_columns = list(feature_columns)

        return self

    def _new_classifier(self):

        try:
            from xgboost import XGBClassifier
        except ImportError as exc:
            raise RuntimeError(
                "XGBoost is not installed. Install project dependencies "
                "with `python3 -m pip install -r requirements.txt`."
            ) from exc

        params = {
            "n_estimators": self.config.n_estimators,
            "max_depth": self.config.max_depth,
            "learning_rate": self.config.learning_rate,
            "subsample": self.config.subsample,
            "colsample_bytree": self.config.colsample_bytree,
            "objective": self.config.objective,
            "eval_metric": self.config.eval_metric,
            "random_state": self.config.random_state,
            "n_jobs": self.config.n_jobs,
            **self.config.extra_params,
        }

        return XGBClassifier(**params)

    def _require_trained(self):

        if self.model is None or not self._feature_columns:
            raise RuntimeError("Train or load the XGBoost model first.")
