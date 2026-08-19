from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ml.dataset import (
    DirectionDatasetConfig,
    DirectionPredictionDatasetBuilder,
)
from ml.features import FeatureConfig, MLFeatureEngine
from ml.xgboost_model import XGBoostDirectionModel


class FakeClassifier:

    def __init__(self):

        self.fit_columns = []
        self.loaded_path = None

    def fit(
        self,
        x,
        y,
    ):

        self.fit_columns = list(x.columns)
        self.fit_target_count = len(y)

        return self

    def predict_proba(
        self,
        x,
    ):

        return np.array([[0.25, 0.75]] * len(x))

    def save_model(
        self,
        path,
    ):

        Path(path).write_text("fake-model")

    def load_model(
        self,
        path,
    ):

        self.loaded_path = path


def candle_frame(rows=80):
    timestamps = pd.date_range(
        "2026-01-01",
        periods=rows,
        freq="5min",
    )
    close = pd.Series(
        [100 + index * 0.5 + (index % 5) for index in range(rows)],
        dtype=float,
    )

    return pd.DataFrame({
        "timestamp": timestamps,
        "open": close - 0.3,
        "high": close + 1.2,
        "low": close - 1.1,
        "close": close,
        "volume": [
            10 + (index % 7) * 2
            for index in range(rows)
        ],
    })


def dataset_builder():
    return DirectionPredictionDatasetBuilder(
        feature_engine=MLFeatureEngine(
            FeatureConfig(drop_warmup=False)
        ),
        config=DirectionDatasetConfig(horizon=3),
    )


def test_xgboost_model_reports_missing_dependency(monkeypatch):
    original_import = __import__

    def fake_import(
        name,
        *args,
        **kwargs,
    ):

        if name == "xgboost":
            raise ImportError("missing test dependency")

        return original_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)
    model = XGBoostDirectionModel()

    with pytest.raises(RuntimeError) as exc:
        model._new_classifier()

    assert "XGBoost is not installed" in str(exc.value)


def test_xgboost_model_trains_with_injected_classifier():
    builder = dataset_builder()
    dataset = builder.build(candle_frame())
    model = XGBoostDirectionModel(dataset_builder=builder)
    fake_classifier = FakeClassifier()
    model._new_classifier = lambda: fake_classifier

    model.train(dataset)
    prediction = model.predict_latest(dataset)

    assert model.feature_columns
    assert fake_classifier.fit_columns == model.feature_columns
    assert fake_classifier.fit_target_count == len(dataset)
    assert prediction.probability_up == 0.75
    assert prediction.predicted_direction == 1
    assert prediction.confidence == 0.75


def test_xgboost_model_requires_training_before_prediction():
    builder = dataset_builder()
    dataset = builder.build(candle_frame())
    model = XGBoostDirectionModel(dataset_builder=builder)

    try:
        model.predict_latest(dataset)
    except RuntimeError as exc:
        assert "Train or load" in str(exc)
    else:
        raise AssertionError("Expected untrained model error.")


def test_xgboost_model_save_and_load(tmp_path):
    builder = dataset_builder()
    dataset = builder.build(candle_frame())
    model_path = tmp_path / "direction.json"

    model = XGBoostDirectionModel(dataset_builder=builder)
    trained_classifier = FakeClassifier()
    model._new_classifier = lambda: trained_classifier
    model.train(dataset)
    model.save(model_path)

    assert model_path.read_text() == "fake-model"

    loaded_classifier = FakeClassifier()
    loaded = XGBoostDirectionModel(dataset_builder=builder)
    loaded._new_classifier = lambda: loaded_classifier
    loaded.load(model_path, model.feature_columns)

    assert loaded.feature_columns == model.feature_columns
    assert loaded_classifier.loaded_path == str(model_path)
