from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

from ml.dataset import DirectionPredictionDatasetBuilder


@dataclass(frozen=True)
class ClassificationMetrics:

    samples: int
    true_positive: int
    true_negative: int
    false_positive: int
    false_negative: int
    accuracy: float
    precision: float
    recall: float
    specificity: float
    f1: float
    brier_score: float
    average_confidence: float
    average_forward_return: float
    predicted_up_forward_return: float
    predicted_down_forward_return: float
    strategy_forward_return: float


@dataclass(frozen=True)
class MLWalkForwardFold:

    fold: int
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    metrics: ClassificationMetrics


@dataclass(frozen=True)
class MLWalkForwardReport:

    folds: list[MLWalkForwardFold]

    @property
    def samples(self) -> int:

        return sum(fold.metrics.samples for fold in self.folds)

    @property
    def average_accuracy(self) -> float:

        return self._weighted_average("accuracy")

    @property
    def average_precision(self) -> float:

        return self._weighted_average("precision")

    @property
    def average_recall(self) -> float:

        return self._weighted_average("recall")

    @property
    def average_strategy_forward_return(self) -> float:

        return self._weighted_average("strategy_forward_return")

    def _weighted_average(
        self,
        metric: str,
    ) -> float:

        if not self.folds or self.samples == 0:
            return 0.0

        return sum(
            getattr(fold.metrics, metric) * fold.metrics.samples
            for fold in self.folds
        ) / self.samples


class DirectionModelEvaluator:

    def __init__(
        self,
        dataset_builder: DirectionPredictionDatasetBuilder | None = None,
        threshold: float = 0.5,
    ):

        self.dataset_builder = (
            dataset_builder or DirectionPredictionDatasetBuilder()
        )
        self.threshold = threshold

    def evaluate(
        self,
        dataset: pd.DataFrame,
        probabilities: np.ndarray | list[float],
    ) -> ClassificationMetrics:

        if dataset.empty:
            raise ValueError("Cannot evaluate an empty direction dataset.")

        probability_up = np.asarray(probabilities, dtype=float)
        if len(probability_up) != len(dataset):
            raise ValueError(
                "Probability count must match the evaluation dataset length."
            )

        target_column = self.dataset_builder.config.target_column
        future_return_column = self.dataset_builder.config.future_return_column

        actual = dataset[target_column].astype(int).to_numpy()
        predicted = (probability_up >= self.threshold).astype(int)
        forward_return = dataset[future_return_column].astype(float).to_numpy()

        true_positive = int(((predicted == 1) & (actual == 1)).sum())
        true_negative = int(((predicted == 0) & (actual == 0)).sum())
        false_positive = int(((predicted == 1) & (actual == 0)).sum())
        false_negative = int(((predicted == 0) & (actual == 1)).sum())

        confidence = np.maximum(probability_up, 1 - probability_up)
        strategy_return = np.where(predicted == 1, forward_return, -forward_return)

        return ClassificationMetrics(
            samples=len(dataset),
            true_positive=true_positive,
            true_negative=true_negative,
            false_positive=false_positive,
            false_negative=false_negative,
            accuracy=self._safe_divide(
                true_positive + true_negative,
                len(dataset),
            ),
            precision=self._safe_divide(
                true_positive,
                true_positive + false_positive,
            ),
            recall=self._safe_divide(
                true_positive,
                true_positive + false_negative,
            ),
            specificity=self._safe_divide(
                true_negative,
                true_negative + false_positive,
            ),
            f1=self._f1(true_positive, false_positive, false_negative),
            brier_score=float(np.mean((probability_up - actual) ** 2)),
            average_confidence=float(np.mean(confidence)),
            average_forward_return=float(np.mean(forward_return)),
            predicted_up_forward_return=self._mean_when(
                forward_return,
                predicted == 1,
            ),
            predicted_down_forward_return=self._mean_when(
                forward_return,
                predicted == 0,
            ),
            strategy_forward_return=float(np.mean(strategy_return)),
        )

    def walk_forward_dataset(
        self,
        dataset: pd.DataFrame,
        model_factory: Callable[[], object],
        train_size: int,
        test_size: int,
        step_size: int | None = None,
    ) -> MLWalkForwardReport:

        self._validate_window_sizes(train_size, test_size, step_size)
        step = step_size or test_size
        sorted_dataset = dataset.sort_values("timestamp").reset_index(drop=True)
        folds = []
        start = 0

        while start + train_size + test_size <= len(sorted_dataset):
            train = sorted_dataset.iloc[start:start + train_size].reset_index(
                drop=True
            )
            test = sorted_dataset.iloc[
                start + train_size:start + train_size + test_size
            ].reset_index(drop=True)

            model = model_factory()
            model.train(train)
            probabilities = model.predict_proba(test)
            metrics = self.evaluate(test, probabilities)

            folds.append(MLWalkForwardFold(
                fold=len(folds) + 1,
                train_start=train["timestamp"].iloc[0],
                train_end=train["timestamp"].iloc[-1],
                test_start=test["timestamp"].iloc[0],
                test_end=test["timestamp"].iloc[-1],
                metrics=metrics,
            ))

            start += step

        return MLWalkForwardReport(folds=folds)

    def walk_forward_candles(
        self,
        candles: pd.DataFrame,
        model_factory: Callable[[], object],
        train_size: int,
        test_size: int,
        step_size: int | None = None,
    ) -> MLWalkForwardReport:

        dataset = self.dataset_builder.build(candles)

        return self.walk_forward_dataset(
            dataset=dataset,
            model_factory=model_factory,
            train_size=train_size,
            test_size=test_size,
            step_size=step_size,
        )

    def _validate_window_sizes(
        self,
        train_size: int,
        test_size: int,
        step_size: int | None,
    ):

        if train_size <= 0:
            raise ValueError("train_size must be greater than zero.")

        if test_size <= 0:
            raise ValueError("test_size must be greater than zero.")

        if step_size is not None and step_size <= 0:
            raise ValueError("step_size must be greater than zero.")

    def _f1(
        self,
        true_positive: int,
        false_positive: int,
        false_negative: int,
    ) -> float:

        precision = self._safe_divide(
            true_positive,
            true_positive + false_positive,
        )
        recall = self._safe_divide(
            true_positive,
            true_positive + false_negative,
        )

        return self._safe_divide(
            2 * precision * recall,
            precision + recall,
        )

    def _safe_divide(
        self,
        numerator: float,
        denominator: float,
    ) -> float:

        if denominator == 0:
            return 0.0

        return float(numerator / denominator)

    def _mean_when(
        self,
        values: np.ndarray,
        mask: np.ndarray,
    ) -> float:

        if not mask.any():
            return 0.0

        return float(np.mean(values[mask]))
