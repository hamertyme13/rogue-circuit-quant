import numpy as np
import pandas as pd
import pytest

from ml.dataset import (
    DirectionDatasetConfig,
    DirectionPredictionDatasetBuilder,
)
from ml.evaluation import DirectionModelEvaluator
from ml.features import FeatureConfig, MLFeatureEngine


class SignReturnModel:

    def train(
        self,
        dataset,
    ):

        return self

    def predict_proba(
        self,
        dataset,
    ):

        return np.where(dataset["return_1"] >= 0, 0.8, 0.2)


def candle_frame(rows=80):
    timestamps = pd.date_range(
        "2026-01-01",
        periods=rows,
        freq="5min",
    )
    close = [
        100 + index + (6 if index % 6 < 3 else -6)
        for index in range(rows)
    ]

    return pd.DataFrame({
        "timestamp": timestamps,
        "open": close,
        "high": [value + 2 for value in close],
        "low": [value - 2 for value in close],
        "close": close,
        "volume": [
            20 + (index % 9)
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


def test_direction_model_evaluator_computes_classifier_metrics():
    builder = dataset_builder()
    dataset = builder.build(candle_frame(rows=20)).head(4).copy()
    dataset["target_direction"] = [1, 0, 1, 0]
    dataset["future_return"] = [0.03, -0.02, 0.01, -0.04]
    evaluator = DirectionModelEvaluator(dataset_builder=builder)

    metrics = evaluator.evaluate(
        dataset,
        probabilities=[0.9, 0.6, 0.4, 0.1],
    )

    assert metrics.samples == 4
    assert metrics.true_positive == 1
    assert metrics.true_negative == 1
    assert metrics.false_positive == 1
    assert metrics.false_negative == 1
    assert metrics.accuracy == 0.5
    assert metrics.precision == 0.5
    assert metrics.recall == 0.5
    assert metrics.specificity == 0.5
    assert metrics.f1 == 0.5
    assert metrics.predicted_up_forward_return == pytest.approx(0.005)
    assert metrics.predicted_down_forward_return == pytest.approx(-0.015)
    assert metrics.strategy_forward_return == pytest.approx(0.01)


def test_direction_model_evaluator_rejects_bad_probability_length():
    builder = dataset_builder()
    dataset = builder.build(candle_frame(rows=20))
    evaluator = DirectionModelEvaluator(dataset_builder=builder)

    with pytest.raises(ValueError):
        evaluator.evaluate(dataset, probabilities=[0.7])


def test_direction_model_walk_forward_builds_ordered_folds():
    builder = dataset_builder()
    evaluator = DirectionModelEvaluator(dataset_builder=builder)
    report = evaluator.walk_forward_candles(
        candles=candle_frame(rows=90),
        model_factory=SignReturnModel,
        train_size=10,
        test_size=5,
        step_size=5,
    )

    assert report.folds
    assert report.samples == len(report.folds) * 5
    assert 0 <= report.average_accuracy <= 1
    assert report.folds[0].fold == 1
    assert report.folds[0].train_start < report.folds[0].test_start
    assert report.folds[-1].test_end > report.folds[0].test_end


def test_direction_model_walk_forward_rejects_invalid_windows():
    evaluator = DirectionModelEvaluator(dataset_builder=dataset_builder())

    with pytest.raises(ValueError):
        evaluator.walk_forward_dataset(
            dataset=pd.DataFrame(),
            model_factory=SignReturnModel,
            train_size=0,
            test_size=5,
        )
